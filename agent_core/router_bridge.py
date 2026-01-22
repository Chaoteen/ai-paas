#!/usr/bin/env python3
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

# =========================
# Path bootstrap (portable)
# =========================
# project root = .../ai-paas
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Optional override: if you keep a separate SDK path, allow env var
# Example: export AIOS_SDK_PATH=/some/path/aios_sdk
AIOS_SDK_PATH = os.getenv("AIOS_SDK_PATH", "")
if AIOS_SDK_PATH and os.path.exists(AIOS_SDK_PATH) and AIOS_SDK_PATH not in sys.path:
    sys.path.insert(0, AIOS_SDK_PATH)

# aios_sdk（gRPC stub）
try:
    from aios_sdk import langgraph_pb2, langgraph_pb2_grpc
    LANGGRAPH_AVAILABLE = True
except Exception:
    LANGGRAPH_AVAILABLE = False

# =========================
# Config
# =========================
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
LANGGRAPH_SERVICE_URL = os.getenv("LANGGRAPH_SERVICE_URL", "localhost:50051")
PROMPTFLOW_SERVICE_URL = os.getenv("PROMPTFLOW_SERVICE_URL", "http://localhost:8081")

SOURCE_STREAM = os.getenv("SOURCE_STREAM", "agent.tasks.stream")
SOURCE_GROUP = os.getenv("SOURCE_GROUP", "router_workers")
DEST_STREAM = os.getenv("DEST_STREAM", "agent.processed.tasks.stream")

# 阻塞读取
READ_COUNT = int(os.getenv("READ_COUNT", "10"))
READ_BLOCK_MS = int(os.getenv("READ_BLOCK_MS", "5000"))

# 防循环/防风暴
MAX_PROCESSING_COUNT = int(os.getenv("MAX_PROCESSING_COUNT", "2"))

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
            "subscribed_agents": data.get("subscribed_agents", ["deepseek-r1:latest"]),
            "routing_policy": data.get("routing_policy", "langgraph_priority"),
            "model_policy": {
                "default_model": data.get("model", "qwen-8b"),
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
        task_type = data.get("task_type") or ""
        return (
            task_type in ["customer_service", "content_generation", "analysis", "summarize"]
            or any(k in content for k in ["help", "assist", "generate", "create", "analyze", "总结", "分析", "帮助", "生成", "创建"])
        )

    async def _preprocess_with_promptflow(self, data: dict, metadata: dict, task_id: str) -> dict:
        if not self._needs_promptflow_preprocessing(data):
            data["promptflow_processed"] = False
            return data

        try:
            logger.info(f"🔄 PromptFlow预处理: {task_id}")
            pf_inputs = {
                "user_message": data.get("content", ""),
                "user_profile": metadata.get("user_profile", {}),
                "agent_profile": metadata.get("agent_profile", {}),
                "memory_hot": data.get("memory_hot", []),
                "memory_cold": data.get("memory_cold", []),
                "retrieved_docs": data.get("retrieved_docs", []),
            }
            pf_result = await self.promptflow_client.execute_flow(pf_inputs)

            enhanced = dict(data)
            enhanced["original_content"] = data.get("content", "")
            # 你之前用 greeting 字段，这里保持兼容；若 pf_result 有其它字段可自行改
            enhanced["content"] = pf_result.get("greeting") or data.get("content", "")
            enhanced["promptflow_processed"] = True
            enhanced["promptflow_trace_id"] = task_id
            enhanced["promptflow_result"] = pf_result
            return enhanced

        except Exception as e:
            logger.warning(f"⚠️ PromptFlow失败，降级使用原始内容: {e}")
            data["promptflow_processed"] = False
            data["promptflow_error"] = str(e)
            return data

    # ---------- LangGraph routing ----------
    async def _get_langgraph_routing(self, data: dict, metadata: dict, task_id: str) -> str:
        if not self.langgraph_stub:
            return await self._fallback_routing(data, metadata)

        try:
            req = langgraph_pb2.RoutingRequest(
                task_id=task_id,
                content=data.get("content", ""),
                task_type=data.get("task_type", ""),
                model=metadata.get("agent_profile", {}).get("model_policy", {}).get("default_model", ""),
                metadata={
                    "promptflow_processed": json.dumps(bool(data.get("promptflow_processed", False))),
                    "original_content": json.dumps(data.get("original_content", "")),
                    "user_profile": json.dumps(metadata.get("user_profile", {})),
                    "agent_profile": json.dumps(metadata.get("agent_profile", {})),
                    "session_context": json.dumps(metadata.get("session_context", {})),
                },
                timestamp=time.time(),
            )
            resp = await self.langgraph_stub.GetRoutingDecision(req)
            logger.info(f"🎯 LangGraph路由: {task_id} → {resp.target_agent} (conf={resp.confidence:.2f})")
            return resp.target_agent

        except Exception as e:
            logger.warning(f"⚠️ LangGraph路由失败，降级: {e}")
            return await self._fallback_routing(data, metadata)

    async def _fallback_routing(self, data: dict, metadata: dict) -> str:
        task_type = (data.get("task_type") or "").lower()
        content = (data.get("content") or "").lower()

        # 优先 subscribed_agents
        subs = metadata.get("agent_profile", {}).get("subscribed_agents") or []
        if subs and subs != ["deepseek-r1:latest"]:
            if task_type:
                candidate = f"agent.{task_type}"
                if candidate in subs:
                    return candidate
            return subs[0]

        # 默认映射
        if task_type in ["translate", "translation"]:
            return "agent.translate"
        if task_type in ["summarize", "summary"]:
            return "deepseek-r1:latest"
        if task_type in ["rewrite", "rewriting"]:
            return "agent.rewrite"
        if task_type in ["code", "programming"]:
            return "agent.code"
        if task_type in ["analyze", "analysis"]:
            return "deepseek-r1:latest"

        if "总结" in content or "summary" in content:
            return "deepseek-r1:latest"
        if "翻译" in content or "translate" in content:
            return "agent.translate"
        if "改写" in content or "rewrite" in content:
            return "agent.rewrite"
        if "代码" in content or "program" in content:
            return "agent.code"
        if "分析" in content or "analy" in content:
            return "deepseek-r1:latest"

        return "deepseek-r1:latest"

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

        if envelope.get("routed_by"):
            logger.warning(f"🔄 已路由消息，跳过: {task_id}")
            return

        # 诊断/测试消息跳过
        if data.get("diagnostic_marker") or data.get("safe_test"):
            logger.info(f"🧪 跳过诊断/测试消息: {task_id}")
            return

        # 1) PromptFlow 一次
        processed_data = await self._preprocess_with_promptflow(data, metadata, task_id)

        # 2) LangGraph 一次
        target_agent = await self._get_langgraph_routing(processed_data, metadata, task_id)
        logger.info(f"✅ 路由完成: {task_id} → {target_agent}")

        # 3) routed_data
        routed_data = dict(processed_data)
        routed_data["ts_pub"] = time.time()
        routed_data["_processing_count"] = processing_count + 1
        routed_data["_router_processed"] = True

        # 4) ✅ 透传 Control Plane 字段（同步匹配关键）
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

        # 5) final_envelope（只构建一次，不要重复构建/重复预处理）
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

            # 标准化 metadata
            "metadata": metadata,
        }

        # 6) 写入 processed stream
        await self.redis_client.xadd(
            DEST_STREAM,
            {"message": json.dumps(final_envelope, ensure_ascii=False)},
            maxlen=10000,
        )
        logger.info(f"📤 已发布到 {DEST_STREAM}: task={task_id} → {target_agent}")

    # ---------- Main loop ----------
    async def start_router(self):
        self.redis_client = redis.from_url(REDIS_URL, decode_responses=True)

        await self._init_langgraph_client()
        await self._initialize_stream_group()

        logger.info(f"🚦 RouterBridge started: {SOURCE_STREAM} -> {DEST_STREAM} (group={SOURCE_GROUP}, consumer={self.consumer_id})")

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
                                raw_msg = msg_data.get("message", "")
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

                                await self._route_to_target(data, session_id, task_id, message_seq, metadata, original_envelope)

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
