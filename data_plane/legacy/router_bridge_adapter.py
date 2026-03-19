"""
LEGACY COMPATIBILITY MODULE

Status:
- Frozen for formal-release governance
- Not part of the formal Gateway -> Tasks API -> Task Store/Outbox -> Redis Queue -> Runtime Workers mainline
- Retained temporarily for historical reference / migration audit only

Rules:
- No new features
- No new production dependencies
- Do not wire this module into formal bootstrap/startup paths
- Candidate for archive/legacy migration after dependency cleanup
"""

#!/usr/bin/env python3
# ai-os/data_plane/legacy/router_bridge_adapter.py

import json
import time
import uuid
import logging
from typing import Any, Dict, Optional, Callable

import redis.asyncio as redis

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class RouterBridgeAdapter:
    """
    legacy -> streams 适配器（冻结）

    目标：
    - 兼容旧的 agent_core/envelope_bus.py（本地 asyncio MessageBus）
    - 将 legacy message 统一封装成标准化 envelope，并写入 Redis Streams: agent.tasks.stream
    - 后续由 agent_core/router_bridge.py 接管：PromptFlow + LangGraph 路由 + 写入 agent.processed.tasks.stream

    注意：
    - 这里不做鉴权、不做路由决策
    - 这里只做“格式标准化 + 入队 Streams”
    """

    def __init__(
        self,
        legacy_bus: Any,
        redis_url: str = "redis://localhost:6379",
        target_stream: str = "agent.tasks.stream",
        maxlen: int = 10000,
    ):
        """
        :param legacy_bus: agent_core/envelope_bus.py 的 MessageBus 实例
        :param redis_url: Redis 连接
        :param target_stream: 写入的 Stream（通常是 agent.tasks.stream）
        """
        self.legacy_bus = legacy_bus
        self.redis_url = redis_url
        self.target_stream = target_stream
        self.maxlen = maxlen
        self.redis_client: Optional[redis.Redis] = None

    async def start(self):
        """初始化 Redis 连接（不负责启动 legacy_bus.start()）"""
        self.redis_client = redis.from_url(self.redis_url, decode_responses=True)
        logger.info("[RouterBridgeAdapter] started, target_stream=%s", self.target_stream)

    async def stop(self):
        if self.redis_client:
            await self.redis_client.aclose()
            self.redis_client = None
        logger.info("[RouterBridgeAdapter] stopped")

    # -------------------------
    # 订阅 legacy bus
    # -------------------------
    def bind_topic(self, topic: str):
        """
        将某个 legacy topic 的消息转发到 Redis Stream
        - topic 一般是旧系统发消息的 topic，比如 "agent.tasks.stream" 或其它业务 topic
        """
        if not self.legacy_bus:
            raise RuntimeError("legacy_bus is required")

        async def _handler(message: Any):
            await self.forward(topic, message)

        # legacy bus subscribe 可能接收 sync 或 async handler
        self.legacy_bus.subscribe(topic, _handler)
        logger.info("[RouterBridgeAdapter] bind_topic: %s", topic)

    # -------------------------
    # 核心转发逻辑
    # -------------------------
    async def forward(self, topic: str, message: Any):
        """
        将 legacy message 转换为标准化 envelope，然后 xadd 到 Redis Stream
        """
        if not self.redis_client:
            raise RuntimeError("Redis client not initialized. Call start() first.")

        # 兼容：message 可能不是 dict
        if isinstance(message, dict):
            data = message
        else:
            data = {"content": str(message)}

        # 标准化 ID
        session_id = data.get("session_id") or f"sess_{uuid.uuid4().hex}"
        task_id = data.get("task_id") or f"task_{uuid.uuid4().hex}"
        message_seq = data.get("message_seq") or 0

        # 透传（如果存在就保留）
        request_id = data.get("request_id")
        envelope_id = data.get("envelope_id")
        tenant_id = data.get("tenant_id")

        # 标准化 metadata（若 legacy 没有就给空）
        metadata = data.get("metadata") or {}

        # 构建标准化 envelope（与你当前 router_bridge.py 的消费逻辑兼容）
        envelope: Dict[str, Any] = {
            "topic": topic,  # 保留 legacy topic
            "data": data,
            "timestamp": time.time(),
            "message_id": str(uuid.uuid4()),
            "session_id": session_id,
            "task_id": task_id,
            "message_seq": message_seq,
            "metadata": metadata,
        }

        # ✅ 同步匹配关键字段：顶层也放一份（如果存在）
        if request_id:
            envelope["request_id"] = request_id
        if envelope_id:
            envelope["envelope_id"] = envelope_id
        if tenant_id:
            envelope["tenant_id"] = tenant_id

        await self.redis_client.xadd(
            self.target_stream,
            {"message": json.dumps(envelope, ensure_ascii=False)},
            maxlen=self.maxlen,
        )

        logger.info(
            "[RouterBridgeAdapter] forwarded -> stream=%s topic=%s session=%s task=%s",
            self.target_stream, topic, session_id, task_id
        )
