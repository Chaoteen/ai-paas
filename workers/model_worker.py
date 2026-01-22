#!/usr/bin/env python3
# ai-os/workers/model_worker.py
from __future__ import annotations

import json
import os
import time
import uuid
import logging
from typing import Any, Dict, Optional

import aiohttp
import asyncio
import redis.asyncio as redis

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("model_worker")

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

PROCESSED_STREAM = os.getenv("DEST_STREAM", "agent.processed.tasks.stream")
RESULT_STREAM = os.getenv("RESULT_STREAM", "agent.result.stream")

GROUP = os.getenv("MODEL_WORKER_GROUP", "model_workers")
CONSUMER = os.getenv("MODEL_WORKER_CONSUMER", f"mw_{uuid.uuid4().hex[:8]}")

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
DEFAULT_MODEL_ID = os.getenv("DEFAULT_MODEL_ID", "deepseek-r1:latest")

READ_COUNT = int(os.getenv("READ_COUNT", "10"))
READ_BLOCK_MS = int(os.getenv("READ_BLOCK_MS", "5000"))

def _extract_model_id(topic: str, metadata: Dict[str, Any], data: Dict[str, Any]) -> str:
    if topic.startswith("agent.model."):
        return topic[len("agent.model."):]

    mp = (metadata.get("agent_profile", {}) or {}).get("model_policy", {}) or {}
    return data.get("model") or mp.get("default_model") or DEFAULT_MODEL_ID

async def call_ollama_generate(model: str, prompt: str) -> str:
    url = f"{OLLAMA_URL.rstrip('/')}/api/generate"
    payload = {"model": model, "prompt": prompt, "stream": False}
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

    async def _init_group(self):
        try:
            await self.r.xgroup_create(name=PROCESSED_STREAM, groupname=GROUP, id="0", mkstream=True)
            logger.info("✅ 创建消费者组: %s", GROUP)
        except Exception as e:
            if "BUSYGROUP" in str(e):
                logger.info("✅ 消费者组已存在: %s", GROUP)
            else:
                raise

    async def _publish_result(self, base_env: Dict[str, Any], status: str, output: Any, model: str, latency_ms: int, error: Optional[str] = None):
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

        logger.info("🚀 ModelWorker started: %s(group=%s consumer=%s) -> %s", PROCESSED_STREAM, GROUP, CONSUMER, RESULT_STREAM)

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

                            model_id = _extract_model_id(topic, metadata, data)
                            prompt = data.get("content") or data.get("user_message") or ""

                            t0 = time.time()
                            output = await call_ollama_generate(model_id, prompt)
                            latency_ms = int((time.time() - t0) * 1000)

                            await self._publish_result(env, "ok", output, model_id, latency_ms)
                            await self.r.xack(PROCESSED_STREAM, GROUP, msg_id)

                            logger.info("✅ 完成 msg=%s tenant=%s model=%s latency=%dms", msg_id, tenant_id, model_id, latency_ms)

                        except Exception as e:
                            logger.error("❌ 执行失败 msg=%s err=%s", msg_id, e)
                            try:
                                await self._publish_result(env if 'env' in locals() else {}, "fail", "", DEFAULT_MODEL_ID, 0, error=str(e))
                            except Exception:
                                pass
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
