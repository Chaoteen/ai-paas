#!/usr/bin/env python3
# ai-os/workers/model_worker.py
from __future__ import annotations

import json
import os
import time
import uuid
import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

import aiohttp
import asyncio
import redis.asyncio as redis

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("model_worker")

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

# RouterBridge writes into DEST_STREAM; ModelWorker consumes it
PROCESSED_STREAM = os.getenv("DEST_STREAM", "agent.processed.tasks.stream")

# ModelWorker writes results here (Gateway/Frontend should subscribe this)
RESULT_STREAM = os.getenv("RESULT_STREAM", "agent.result.stream")

GROUP = os.getenv("MODEL_WORKER_GROUP", "model_workers")
CONSUMER = os.getenv("MODEL_WORKER_CONSUMER", f"mw_{uuid.uuid4().hex[:8]}")

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
DEFAULT_MODEL_ID = os.getenv("DEFAULT_MODEL_ID", "deepseek-r1:latest")

READ_COUNT = int(os.getenv("READ_COUNT", "10"))
READ_BLOCK_MS = int(os.getenv("READ_BLOCK_MS", "5000"))

# Pipeline config
PIPELINES_PATH = os.getenv("PIPELINES_PATH", "config/pipelines.yaml")


# -------------------------
# Utilities
# -------------------------
def _extract_model_id(topic: str, metadata: Dict[str, Any], data: Dict[str, Any]) -> str:
    """
    topic: agent.model.<ollama_model_id>
    fallback: metadata.agent_profile.model_policy.default_model or DEFAULT_MODEL_ID
    """
    if topic.startswith("agent.model."):
        return topic[len("agent.model."):].strip() or DEFAULT_MODEL_ID

    mp = (metadata.get("agent_profile", {}) or {}).get("model_policy", {}) or {}
    return (data.get("model") or mp.get("default_model") or DEFAULT_MODEL_ID).strip() or DEFAULT_MODEL_ID


def _extract_trace_and_pipeline(env: Dict[str, Any]) -> Tuple[Optional[str], str]:
    data = env.get("data", {}) if isinstance(env.get("data"), dict) else {}
    trace_id = env.get("trace_id") or data.get("trace_id")

    # Prefer top-level pipeline_id (RouterBridge already duplicates it)
    pipeline_id = (env.get("pipeline_id") or "").strip()
    if not pipeline_id:
        routing = data.get("routing", {}) if isinstance(data.get("routing"), dict) else {}
        pipeline_id = (routing.get("pipeline_id") or "").strip()

    return trace_id, (pipeline_id or "default_v1")


def _load_yaml(path: str) -> Optional[dict]:
    try:
        import yaml  # type: ignore
    except Exception:
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except Exception:
        return None


@dataclass(frozen=True)
class PipelineSpec:
    pipeline_id: str
    description: str
    system: str
    options: Dict[str, Any]


class PipelineRegistry:
    """
    Production-ish pipeline registry:
    - file based (pipelines.yaml) so it can be managed by ops
    - has safe defaults if config missing/broken
    - exposes get(pipeline_id) with fallback to default
    """

    def __init__(self, path: str):
        self.path = path
        self.default_pipeline = "default_v1"
        self._pipelines: Dict[str, PipelineSpec] = {}
        self.reload()

    def reload(self) -> None:
        data = _load_yaml(self.path) if os.path.exists(self.path) else None
        if not isinstance(data, dict):
            logger.warning("⚠️ pipelines config missing/invalid: %s (fallback to built-in defaults)", self.path)
            self._load_builtin()
            return

        default_pipeline = str(data.get("default_pipeline") or "default_v1").strip() or "default_v1"
        raw = data.get("pipelines") or {}
        if not isinstance(raw, dict):
            logger.warning("⚠️ pipelines.pipelines is not a dict (fallback to built-in defaults)")
            self._load_builtin()
            return

        pipelines: Dict[str, PipelineSpec] = {}
        for pid, cfg in raw.items():
            if not isinstance(cfg, dict):
                continue
            system = str(cfg.get("system") or "").strip()
            desc = str(cfg.get("description") or "").strip()
            options = cfg.get("options") if isinstance(cfg.get("options"), dict) else {}

            # Guard: system prompt must exist, otherwise pipeline is not useful
            if not system:
                continue

            pipelines[str(pid)] = PipelineSpec(
                pipeline_id=str(pid),
                description=desc,
                system=system,
                options=dict(options),
            )

        if not pipelines:
            logger.warning("⚠️ no valid pipelines parsed (fallback to built-in defaults)")
            self._load_builtin()
            return

        self._pipelines = pipelines
        self.default_pipeline = default_pipeline if default_pipeline in pipelines else list(pipelines.keys())[0]
        logger.info("✅ pipelines loaded: %d (default=%s) from %s", len(pipelines), self.default_pipeline, self.path)

    def _load_builtin(self) -> None:
        # Minimal safe built-ins (should match config semantics)
        self._pipelines = {
            "default_v1": PipelineSpec(
                pipeline_id="default_v1",
                description="General assistant",
                system="You are a helpful assistant. Follow the user's request accurately and concisely.",
                options={"temperature": 0.2, "num_predict": 512},
            ),
            "translate_v1": PipelineSpec(
                pipeline_id="translate_v1",
                description="Translation",
                system=(
                    "You are a professional translator.\n"
                    "Translate accurately and naturally.\n"
                    "Output ONLY the translated text, no extra explanation."
                ),
                options={"temperature": 0.1, "num_predict": 256},
            ),
            "summarize_v1": PipelineSpec(
                pipeline_id="summarize_v1",
                description="Summarization",
                system=(
                    "You are an expert summarizer.\n"
                    "Output:\n"
                    "- Title: <one short title>\n"
                    "- Key points: 3-6 bullets\n"
                    "- Risks/Next steps: 1-3 bullets (if applicable)\n"
                    "Keep it concise and actionable."
                ),
                options={"temperature": 0.2, "num_predict": 512},
            ),
            "code_v1": PipelineSpec(
                pipeline_id="code_v1",
                description="Coding",
                system=(
                    "You are a senior software engineer.\n"
                    "Provide runnable code when appropriate.\n"
                    "Be explicit about assumptions and edge cases."
                ),
                options={"temperature": 0.2, "num_predict": 1024},
            ),
        }
        self.default_pipeline = "default_v1"
        logger.info("✅ pipelines fallback built-in loaded (default=%s)", self.default_pipeline)

    def get(self, pipeline_id: str) -> PipelineSpec:
        pid = (pipeline_id or "").strip()
        if pid and pid in self._pipelines:
            return self._pipelines[pid]
        return self._pipelines.get(self.default_pipeline) or next(iter(self._pipelines.values()))


async def call_ollama_generate(model: str, user_prompt: str, system_prompt: str, options: Dict[str, Any]) -> str:
    """
    Ollama /api/generate supports:
      - model
      - prompt
      - system (optional)
      - options (optional)
      - stream
    """
    url = f"{OLLAMA_URL.rstrip('/')}/api/generate"
    payload: Dict[str, Any] = {
        "model": model,
        "prompt": user_prompt,
        "stream": False,
    }
    if system_prompt:
        payload["system"] = system_prompt
    if options:
        payload["options"] = options

    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=180)) as resp:
            if resp.status != 200:
                txt = await resp.text()
                raise RuntimeError(f"Ollama调用失败: {resp.status} {txt}")
            j = await resp.json()
            return j.get("response", "")


class ModelWorker:
    def __init__(self):
        self.r: Optional[redis.Redis] = None
        self.running = True
        self.registry = PipelineRegistry(PIPELINES_PATH)

    async def _init_group(self):
        try:
            await self.r.xgroup_create(name=PROCESSED_STREAM, groupname=GROUP, id="0", mkstream=True)
            logger.info("✅ 创建消费者组: %s", GROUP)
        except Exception as e:
            if "BUSYGROUP" in str(e):
                logger.info("✅ 消费者组已存在: %s", GROUP)
            else:
                raise

    async def _publish_result(
        self,
        base_env: Dict[str, Any],
        status: str,
        output: Any,
        model: str,
        latency_ms: int,
        trace_id: Optional[str],
        pipeline_id: str,
        error: Optional[str] = None,
    ):
        res_env = {
            "topic": "agent.result",
            "timestamp": time.time(),
            "message_id": str(uuid.uuid4()),

            "tenant_id": base_env.get("tenant_id"),
            "request_id": base_env.get("request_id"),
            "envelope_id": base_env.get("envelope_id"),
            "session_id": base_env.get("session_id"),
            "task_id": base_env.get("task_id"),
            "message_seq": base_env.get("message_seq", 0),

            # correlation / observability
            "trace_id": trace_id,
            "pipeline_id": pipeline_id,

            "status": status,
            "model": model,
            "latency_ms": latency_ms,
            "output": output,
        }
        if error:
            res_env["error"] = error

        await self.r.xadd(RESULT_STREAM, {"message": json.dumps(res_env, ensure_ascii=False)}, maxlen=10000)

    async def run(self):
        self.r = redis.from_url(REDIS_URL, decode_responses=True)
        await self._init_group()

        logger.info(
            "🚀 ModelWorker started: %s(group=%s consumer=%s) -> %s | pipelines=%s",
            PROCESSED_STREAM, GROUP, CONSUMER, RESULT_STREAM, PIPELINES_PATH
        )

        while self.running:
            try:
                msgs = await self.r.xreadgroup(
                    groupname=GROUP,
                    consumername=CONSUMER,
                    streams={PROCESSED_STREAM: ">"},
                    count=READ_COUNT,
                    block=READ_BLOCK_MS,
                )
                if not msgs:
                    continue

                for _stream, lst in msgs:
                    for msg_id, fields in lst:
                        env: Dict[str, Any] = {}
                        try:
                            raw = fields.get("message", "")
                            if not raw:
                                await self.r.xack(PROCESSED_STREAM, GROUP, msg_id)
                                continue

                            env = json.loads(raw)
                            topic = env.get("topic", "")
                            data = env.get("data", {}) if isinstance(env.get("data"), dict) else {}
                            metadata = env.get("metadata", {}) if isinstance(env.get("metadata"), dict) else {}

                            if not topic.startswith("agent.model."):
                                logger.info("⏭️ 跳过非模型任务 topic=%s msg=%s", topic, msg_id)
                                await self.r.xack(PROCESSED_STREAM, GROUP, msg_id)
                                continue

                            tenant_id = env.get("tenant_id") or data.get("tenant_id")
                            if not tenant_id:
                                logger.error("🚫 tenant_id缺失，拒绝执行 msg=%s", msg_id)
                                await self.r.xack(PROCESSED_STREAM, GROUP, msg_id)
                                continue

                            trace_id, pipeline_id = _extract_trace_and_pipeline(env)
                            spec = self.registry.get(pipeline_id)

                            model_id = _extract_model_id(topic, metadata, data)
                            user_prompt = data.get("content") or data.get("user_message") or ""

                            # Production guard: empty prompt => still publish fail for observability
                            if not user_prompt.strip():
                                await self._publish_result(
                                    env, "fail", "", model_id, 0, trace_id, pipeline_id, error="empty_prompt"
                                )
                                await self.r.xack(PROCESSED_STREAM, GROUP, msg_id)
                                continue

                            logger.info(
                                "🧩 exec msg=%s tenant=%s trace=%s pipeline=%s model=%s",
                                msg_id, tenant_id, trace_id, spec.pipeline_id, model_id
                            )

                            t0 = time.time()
                            output = await call_ollama_generate(
                                model=model_id,
                                user_prompt=user_prompt,
                                system_prompt=spec.system,
                                options=spec.options,
                            )
                            latency_ms = int((time.time() - t0) * 1000)

                            await self._publish_result(env, "ok", output, model_id, latency_ms, trace_id, spec.pipeline_id)
                            await self.r.xack(PROCESSED_STREAM, GROUP, msg_id)

                            logger.info(
                                "✅ 完成 msg=%s tenant=%s trace=%s pipeline=%s model=%s latency=%dms",
                                msg_id, tenant_id, trace_id, spec.pipeline_id, model_id, latency_ms
                            )

                        except Exception as e:
                            logger.error("❌ 执行失败 msg=%s err=%s", msg_id, e)
                            try:
                                trace_id, pipeline_id = _extract_trace_and_pipeline(env) if env else (None, "default_v1")
                                await self._publish_result(env if env else {}, "fail", "", DEFAULT_MODEL_ID, 0, trace_id, pipeline_id, error=str(e))
                            except Exception:
                                pass
                            # NOTE: 当前仍然 ack（与你之前一致）；后续我们单独一轮把失败改成 DLQ/不 ack 可重试
                            await self.r.xack(PROCESSED_STREAM, GROUP, msg_id)

            except Exception as e:
                if "NOGROUP" in str(e):
                    await self._init_group()
                else:
                    logger.error("❌ xreadgroup错误: %s", e)
                    await asyncio.sleep(1)

    async def stop(self):
        self.running = False
        if self.r:
            await self.r.aclose()


async def main():
    w = ModelWorker()
    try:
        await w.run()
    except KeyboardInterrupt:
        await w.stop()


if __name__ == "__main__":
    asyncio.run(main())
