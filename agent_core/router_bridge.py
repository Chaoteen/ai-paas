#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ai-os/agent_core/router_bridge.py

import sys
import os
import json
import time
import uuid
import asyncio
import logging
from typing import Dict, Any, Optional, Tuple

import aiohttp
import grpc
import redis.asyncio as redis

# aios_sdk envelope (StandardMetadata)
try:
    from aios_sdk import envelope_pb2  # type: ignore
    ENVELOPE_AVAILABLE = True
except Exception:
    envelope_pb2 = None  # type: ignore
    ENVELOPE_AVAILABLE = False

# =========================
# Path bootstrap (portable)
# =========================
# project root = .../ai-paas
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Optional override: if you keep a separate SDK path, allow env var
AIOS_SDK_PATH = os.getenv("AIOS_SDK_PATH", "")
if AIOS_SDK_PATH and os.path.exists(AIOS_SDK_PATH) and AIOS_SDK_PATH not in sys.path:
    sys.path.insert(0, AIOS_SDK_PATH)

# aios_sdk（gRPC stub）
try:
    from aios_sdk import langgraph_pb2, langgraph_pb2_grpc  # type: ignore
    LANGGRAPH_AVAILABLE = True
except Exception:
    langgraph_pb2 = None  # type: ignore
    langgraph_pb2_grpc = None  # type: ignore
    LANGGRAPH_AVAILABLE = False

# =========================
# Config
# =========================
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

# LangGraph gRPC addr
LANGGRAPH_SERVICE_URL = os.getenv("LANGGRAPH_SERVICE_URL", "127.0.0.1:50051")

# PromptFlow HTTP base
PROMPTFLOW_SERVICE_URL = os.getenv("PROMPTFLOW_SERVICE_URL", "http://127.0.0.1:8080")

# Streams
SOURCE_STREAM = os.getenv("SOURCE_STREAM", "agent.tasks.stream")
SOURCE_GROUP = os.getenv("SOURCE_GROUP", "router_workers")
DEST_STREAM = os.getenv("DEST_STREAM", "agent.processed.tasks.stream")

# Blocking read
READ_COUNT = int(os.getenv("READ_COUNT", "10"))
READ_BLOCK_MS = int(os.getenv("READ_BLOCK_MS", "5000"))

# Anti-loop / storm guard
MAX_PROCESSING_COUNT = int(os.getenv("MAX_PROCESSING_COUNT", "2"))

# IMPORTANT: MUST be a real runnable model id
DEFAULT_AGENT = os.getenv("DEFAULT_AGENT", "deepseek-r1:latest")

# maxlen for processed stream
DEST_MAXLEN = int(os.getenv("DEST_MAXLEN", "10000"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("router_bridge")


# =========================
# PromptFlow client
# =========================
class PromptFlowClient:
    def __init__(self, base_url: str = PROMPTFLOW_SERVICE_URL):
        self.base_url = base_url.rstrip("/")
        self.score_url = f"{self.base_url}/score"

    async def execute_flow(self, inputs: dict) -> dict:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                self.score_url,
                json=inputs,
                headers={"Content-Type": "application/json"},
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    raise RuntimeError(f"PromptFlow调用失败: {resp.status} - {body}")
                return await resp.json()


# =========================
# LangGraph routing normalize (PROD CONTRACT)
# =========================
def normalize_langgraph_routing(resp: Any) -> Dict[str, Any]:
    """
    Normalize LangGraph RoutingResponse into router_bridge standardized routing dict.

    PROD CONTRACT:
      - pipeline_id MUST come from resp.parameters["pipeline_id"]
      - strategy MUST come from resp.routing_strategy
      - target_agent MUST be a real runnable model id
    """
    params = {}
    try:
        params = getattr(resp, "parameters", None) or {}
    except Exception:
        params = {}

    pipeline_id = ""
    try:
        pipeline_id = (params.get("pipeline_id") or "").strip()
    except Exception:
        pipeline_id = ""

    strategy = ""
    try:
        strategy = (getattr(resp, "routing_strategy", "") or "").strip()
    except Exception:
        strategy = ""

    reasoning = ""
    try:
        reasoning = (getattr(resp, "reasoning", "") or "").strip()
    except Exception:
        reasoning = ""

    confidence = 0.0
    try:
        confidence = float(getattr(resp, "confidence", 0.0) or 0.0)
    except Exception:
        confidence = 0.0

    target_agent = ""
    try:
        target_agent = (getattr(resp, "target_agent", "") or "").strip()
    except Exception:
        target_agent = ""

    # Hard guard: do NOT allow empty pipeline_id to enter Data Plane
    if not pipeline_id:
        pipeline_id = "default_v1"
        if reasoning:
            reasoning = f"{reasoning} | WARN: missing pipeline_id->default_v1"
        else:
            reasoning = "WARN: missing pipeline_id->default_v1"

    return {
        "strategy": strategy,
        "confidence": confidence,
        "reasoning": reasoning,
        "pipeline_id": pipeline_id,
        "target_agent": target_agent,
    }


# =========================
# RouterBridge
# =========================
class RouterBridge:
    """
    职责（冻结）：
    1) 从 agent.tasks.stream 消费消息
    2) 标准化 metadata
    3) 可选：PromptFlow 预处理（一次）
    4) LangGraph 路由决策（一次）
    5) 组装 final_envelope 并写入 agent.processed.tasks.stream
    6) xack 原消息
    """

    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None
        self.langgraph_channel: Optional[grpc.aio.Channel] = None
        self.langgraph_stub = None
        self.promptflow_client = PromptFlowClient()
        self.running = True

        # session 序列号（可选）
        self.session_sequences: Dict[str, int] = {}

        # consumer id（固定一个，避免每次循环换 consumer）
        self.consumer_id = f"router_{uuid.uuid4().hex[:8]}"

    # ---------- LangGraph ----------
    async def _init_langgraph_client(self):
        if not LANGGRAPH_AVAILABLE:
            logger.warning("⚠️ aios_sdk不可用，LangGraph路由将降级为本地 fallback")
            self.langgraph_stub = None
            return
        try:
            self.langgraph_channel = grpc.aio.insecure_channel(LANGGRAPH_SERVICE_URL)
            # 固定 Stub（你 gRPC 冒烟已验证是这个）
            self.langgraph_stub = langgraph_pb2_grpc.LangGraphRouterStub(self.langgraph_channel)
            logger.info("✅ LangGraph客户端初始化成功")
        except Exception as e:
            logger.error(f"❌ LangGraph客户端初始化失败: {e}")
            self.langgraph_stub = None

    # ---------- Stream group ----------
    async def _initialize_stream_group(self):
        try:
            await self.redis_client.xgroup_create(
                name=SOURCE_STREAM,
                groupname=SOURCE_GROUP,
                id="0",
                mkstream=True,
            )
            logger.info(f"✅ 创建源Stream消费者组: {SOURCE_GROUP}")
        except Exception as e:
            if "BUSYGROUP" in str(e):
                logger.info(f"✅ 源Stream消费者组已存在: {SOURCE_GROUP}")
            else:
                raise

    # ---------- Metadata ----------
    def _extract_standardized_metadata(self, data: dict, envelope: dict) -> dict:
        user_profile = {
            "user_id": data.get("user_id") or envelope.get("user_id"),
            "tenant_id": data.get("tenant_id") or envelope.get("tenant_id"),
            "department": data.get("department") or envelope.get("department"),
            "role": data.get("role") or envelope.get("role"),
            "permissions": data.get("permissions") or ["default_access"],
            "technical_level": data.get("technical_level") or envelope.get("technical_level") or "beginner",
        }
        user_profile = {k: v for k, v in user_profile.items() if v is not None}

        agent_profile = {
            "subscribed_agents": data.get("subscribed_agents", [DEFAULT_AGENT]),
            "routing_policy": data.get("routing_policy", "langgraph_priority"),
            "model_policy": {
                "default_model": data.get("model", ""),  # NOTE: may be empty; LangGraph will decide
                "fallback_chain": data.get("fallback_models", ["qwen-4b"]),
                "temperature": data.get("temperature", 0.2),
                "max_tokens": data.get("max_tokens", 2048),
            },
        }

        session_context = {
            "context_window": data.get("context_window", 4096),
            "memory_policy": data.get("memory_policy", "hot_cold_split"),
        }

        return {
            "user_profile": user_profile,
            "agent_profile": agent_profile,
            "session_context": session_context,
        }

    # ---------- IDs ----------
    def _generate_task_ids(self, envelope: dict, data: dict) -> Tuple[str, str, int]:
        session_id = data.get("session_id") or envelope.get("session_id")
        task_id = data.get("task_id") or envelope.get("task_id")

        if not session_id:
            base = task_id or uuid.uuid4().hex
            session_id = f"sess_{base}"
            logger.warning(f"⚠️ 未找到session_id，生成: {session_id}")

        if not task_id:
            task_id = f"task_{uuid.uuid4().hex}"
            logger.warning(f"⚠️ 未找到task_id，生成: {task_id}")

        if session_id not in self.session_sequences:
            self.session_sequences[session_id] = 0
        message_seq = self.session_sequences[session_id]
        self.session_sequences[session_id] += 1

        return session_id, task_id, message_seq

    # ---------- PromptFlow ----------
    def _needs_promptflow_preprocessing(self, data: dict) -> bool:
        content = (data.get("content") or "").lower()
        task_type = (data.get("task_type") or "").lower()
        return (
            task_type in ["customer_service", "content_generation", "analysis", "summarize", "summary"]
            or any(k in content for k in ["help", "assist", "generate", "create", "analyze", "总结", "分析", "帮助", "生成", "创建"])
        )

    async def _preprocess_with_promptflow(self, data: dict, metadata: dict, task_id: str) -> dict:
        if not self._needs_promptflow_preprocessing(data):
            data["promptflow_processed"] = False
            return data

        try:
            logger.info(f"🔄 PromptFlow预处理: {task_id}")

            # ✅ 适配当前 PromptFlow serving 的 swagger schema：输入字段叫 name
            pf_inputs = {"name": data.get("content", "")}
            pf_result = await self.promptflow_client.execute_flow(pf_inputs)

            enhanced = dict(data)
            enhanced["original_content"] = data.get("content", "")

            # ⚠️ 关键修复：绝不覆盖 content（否则会出现 Hello, World!）
            enhanced["content"] = data.get("content", "")

            enhanced["promptflow_processed"] = True
            enhanced["promptflow_applied"] = False
            enhanced["promptflow_trace_id"] = task_id
            enhanced["promptflow_result"] = pf_result
            return enhanced

        except Exception as e:
            logger.warning(f"⚠️ PromptFlow失败，降级使用原始内容: {e}")
            data["promptflow_processed"] = False
            data["promptflow_error"] = str(e)
            return data

    # ---------- LangGraph routing ----------
    def _build_langgraph_metadata(self, data: dict, std_meta: dict):
        """Build ai.os.envelope.StandardMetadata if available; otherwise return None."""
        try:
            if not ENVELOPE_AVAILABLE or envelope_pb2 is None:
                return None
            if not hasattr(envelope_pb2, "StandardMetadata"):
                return None

            m = envelope_pb2.StandardMetadata()
            field_names = {f.name for f in m.DESCRIPTOR.fields}

            user_profile = (std_meta or {}).get("user_profile") or {}
            candidates = {
                "tenant_id": data.get("tenant_id") or user_profile.get("tenant_id"),
                "user_id": data.get("user_id") or user_profile.get("user_id"),
                "session_id": data.get("session_id"),
                "task_id": data.get("task_id"),
            }

            for k, v in candidates.items():
                if v is None:
                    continue
                if k in field_names:
                    try:
                        setattr(m, k, str(v))
                    except Exception:
                        pass

            return m
        except Exception:
            return None

    async def _get_langgraph_routing(self, data: dict, metadata: dict, task_id: str):
        """
        Returns: RoutingResponse-like object (from pb2), or None if unavailable (caller will fallback).
        """
        if not self.langgraph_stub:
            return None

        try:
            # Note: model here is informational (default_model), not the final target_agent.
            default_model = metadata.get("agent_profile", {}).get("model_policy", {}).get("default_model", "")

            req = langgraph_pb2.RoutingRequest(
                task_id=task_id,
                content=data.get("content", ""),
                task_type=data.get("task_type", ""),
                model=default_model,
                metadata=self._build_langgraph_metadata(data, metadata),
                timestamp=time.time(),
            )
            resp = await self.langgraph_stub.GetRoutingDecision(req, timeout=3.0)
            logger.info(f"🎯 LangGraph路由: {task_id} → {resp.target_agent} (conf={resp.confidence:.2f})")
            return resp

        except Exception as e:
            logger.warning(f"⚠️ LangGraph路由失败，降级: {e}")
            return None

    def _fallback_routing_prod(self, data: dict, metadata: dict) -> Dict[str, Any]:
        """
        PROD fallback: MUST return runnable model id and a pipeline_id.
        Never return 'agent.translate' etc.
        """
        task_type = (data.get("task_type") or "").lower()
        content = (data.get("content") or "").lower()

        # Default runnable model
        model = DEFAULT_AGENT

        # allow agent_profile subscribed_agents to override, but ensure it's a runnable model id
        subs = metadata.get("agent_profile", {}).get("subscribed_agents") or []
        if subs:
            # pick first subscribed model that looks non-empty
            if isinstance(subs, list) and subs[0]:
                model = str(subs[0])

        # pipeline heuristic (temporary until full pipeline registry)
        if task_type in ("translate", "translation") or ("翻译" in content) or ("translate" in content):
            pipeline_id = "translate_v1"
        elif task_type in ("summarize", "summary") or ("总结" in content) or ("tl;dr" in content) or ("概括" in content):
            pipeline_id = "summarize_v1"
        elif task_type in ("code", "programming") or any(k in content for k in ["代码", "bug", "报错", "traceback", "exception", "stack"]):
            pipeline_id = "code_v1"
        else:
            pipeline_id = "default_v1"

        return {
            "target_agent": model,
            "routing": {
                "strategy": "fallback",
                "confidence": 0.0,
                "reasoning": "fallback_routing_prod",
                "pipeline_id": pipeline_id,
            },
        }

    # ---------- Core route ----------
    async def _route_to_target(
        self,
        data: dict,
        session_id: str,
        task_id: str,
        message_seq: int,
        metadata: dict,
        envelope: dict,
    ):
        # 防循环
        processing_count = int(data.get("_processing_count", 0) or 0)
        if processing_count >= MAX_PROCESSING_COUNT:
            logger.error(f"🚫 processing_count超限: {task_id} ({processing_count})")
            return

        # 防重复路由：只看顶层 envelope 是否被 routed_by 标记（避免 data 内误伤）
        if envelope.get("routed_by"):
            logger.warning(f"🔄 已路由消息，跳过: {task_id}")
            return

        # 诊断/测试消息跳过
        if data.get("diagnostic_marker") or data.get("safe_test"):
            logger.info(f"🧪 跳过诊断/测试消息: {task_id}")
            return

        # 1) PromptFlow 一次
        processed_data = await self._preprocess_with_promptflow(data, metadata, task_id)

        # 2) LangGraph 一次（若失败则 prod-fallback）
        resp = await self._get_langgraph_routing(processed_data, metadata, task_id)
        if resp is not None:
            r = normalize_langgraph_routing(resp)
            target_agent = r["target_agent"] or DEFAULT_AGENT
            routing = {
                "strategy": r["strategy"],
                "confidence": r["confidence"],
                "reasoning": r["reasoning"],
                "pipeline_id": r["pipeline_id"],
            }
        else:
            fb = self._fallback_routing_prod(processed_data, metadata)
            target_agent = fb["target_agent"]
            routing = fb["routing"]

        logger.info(f"✅ 路由完成: {task_id} → {target_agent} (pipeline={routing.get('pipeline_id')})")

        # 3) routed_data
        routed_data = dict(processed_data)
        routed_data["routing"] = routing
        routed_data["ts_pub"] = time.time()
        routed_data["_processing_count"] = processing_count + 1
        routed_data["_router_processed"] = True

        # 4) 透传 Control Plane 字段（同步匹配关键）
        request_id = envelope.get("request_id") or data.get("request_id")
        envelope_id = envelope.get("envelope_id") or data.get("envelope_id")
        tenant_id = (
            envelope.get("tenant_id")
            or data.get("tenant_id")
            or metadata.get("user_profile", {}).get("tenant_id")
        )

        if request_id:
            routed_data["request_id"] = request_id
        if envelope_id:
            routed_data["envelope_id"] = envelope_id
        if tenant_id:
            routed_data["tenant_id"] = tenant_id

        # 5) final_envelope（只构建一次）
        final_envelope = {
            "topic": f"agent.model.{target_agent}",
            "data": routed_data,
            "timestamp": time.time(),
            "message_id": str(uuid.uuid4()),
            "session_id": session_id,
            "task_id": task_id,
            "message_seq": message_seq,

            # 路由信息
            "routed_by": "router_bridge_standardized",
            "target_agent": target_agent,
            "original_task_id": task_id,
            "routing_chain": ["router_bridge_standardized"],

            # PromptFlow痕迹（顶层便于排查）
            "promptflow_processed": bool(routed_data.get("promptflow_processed", False)),
            "promptflow_trace_id": routed_data.get("promptflow_trace_id"),
            "original_content": routed_data.get("original_content"),

            # ✅ 同步匹配关键字段：顶层也放一份
            "request_id": request_id,
            "envelope_id": envelope_id,
            "tenant_id": tenant_id,

            # ✅ 上线排障友好：顶层冗余 pipeline_id（可选但推荐）
            "pipeline_id": routing.get("pipeline_id", "default_v1"),

            # 标准化 metadata
            "metadata": metadata,
        }

        # 6) 写入 processed stream
        await self.redis_client.xadd(
            DEST_STREAM,
            {"message": json.dumps(final_envelope, ensure_ascii=False)},
            maxlen=DEST_MAXLEN,
        )
        logger.info(f"📤 已发布到 {DEST_STREAM}: task={task_id} → {target_agent}")

    # ---------- Main loop ----------
    async def start_router(self):
        self.redis_client = redis.from_url(REDIS_URL, decode_responses=True)

        await self._init_langgraph_client()
        await self._initialize_stream_group()

        logger.info(
            f"🚦 RouterBridge started: {SOURCE_STREAM} -> {DEST_STREAM} "
            f"(group={SOURCE_GROUP}, consumer={self.consumer_id}, default_agent={DEFAULT_AGENT})"
        )
        logger.info("RB_BUILD: normalize_langgraph_routing@%s", normalize_langgraph_routing.__code__.co_firstlineno)
        logger.info("RB_BUILD: file=%s", __file__)


        try:
            while self.running:
                try:
                    messages = await self.redis_client.xreadgroup(
                        groupname=SOURCE_GROUP,
                        consumername=self.consumer_id,
                        streams={SOURCE_STREAM: ">"},
                        count=READ_COUNT,
                        block=READ_BLOCK_MS,
                    )

                    if not messages:
                        continue

                    for _stream_name, msg_list in messages:
                        for msg_id, msg_data in msg_list:
                            try:
                                raw_msg = (msg_data.get("message") or msg_data.get("data") or "")
                                if not raw_msg:
                                    await self.redis_client.xack(SOURCE_STREAM, SOURCE_GROUP, msg_id)
                                    continue

                                envelope = json.loads(raw_msg)

                                # 兼容：标准 envelope(topic,data) 或 直接 data
                                if isinstance(envelope, dict) and "data" in envelope and "topic" in envelope:
                                    data = envelope.get("data") or {}
                                    original_envelope = envelope
                                else:
                                    data = envelope if isinstance(envelope, dict) else {}
                                    original_envelope = {"topic": "unknown", "data": data}

                                session_id, task_id, message_seq = self._generate_task_ids(original_envelope, data)
                                metadata = self._extract_standardized_metadata(data, original_envelope)

                                await self._route_to_target(
                                    data=data,
                                    session_id=session_id,
                                    task_id=task_id,
                                    message_seq=message_seq,
                                    metadata=metadata,
                                    envelope=original_envelope,
                                )

                                # ack
                                await self.redis_client.xack(SOURCE_STREAM, SOURCE_GROUP, msg_id)

                            except json.JSONDecodeError as e:
                                logger.error(f"❌ JSON解析失败: {e}")
                                await self.redis_client.xack(SOURCE_STREAM, SOURCE_GROUP, msg_id)
                            except Exception as e:
                                logger.error(f"❌ 处理消息失败: {e}")
                                await asyncio.sleep(0.2)

                except Exception as e:
                    if "NOGROUP" in str(e):
                        logger.warning("🔄 消费者组不存在，重建...")
                        await self._initialize_stream_group()
                    else:
                        logger.error(f"❌ xreadgroup异常: {e}")
                        await asyncio.sleep(1)

        finally:
            if self.redis_client:
                await self.redis_client.aclose()
            if self.langgraph_channel:
                await self.langgraph_channel.close()

    async def stop(self):
        self.running = False


async def main():
    rb = RouterBridge()
    try:
        await rb.start_router()
    except KeyboardInterrupt:
        logger.info("收到停止信号，退出")
        await rb.stop()


if __name__ == "__main__":
    asyncio.run(main())
