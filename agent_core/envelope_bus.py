# ai-os/agent_core/envelope_bus.py
from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

Handler = Callable[[Dict[str, Any]], Any]


# ==========================================================
# 标准化 Envelope / Context（与 redis_bus.py 对齐）
# ==========================================================
class StandardizedMessageProcessor:
    """
    标准化 envelope（内存版与 Redis 版保持一致）:

    {
      "topic": "...",
      "data": {...},
      "timestamp": ...,
      "message_id": "...",

      "tenant_id": "...",
      "session_id": "...",
      "task_id": "...",
      "message_seq": ...,
      "request_id": "...",
      "envelope_id": "...",

      "metadata": {...}
    }

    processing_context:
    {
      "envelope": <envelope dict>,
      "topic": "...",
      "raw_data": ...,
      "metadata": {...},

      "tenant_id": ...,
      "session_id": ...,
      "task_id": ...,
      "message_seq": ...,
      "request_id": ...,
      "envelope_id": ...,

      "bus_message_id": <message_id>,
    }
    """

    @staticmethod
    def _safe_dict(x: Any) -> Dict[str, Any]:
        return x if isinstance(x, dict) else {}

    @classmethod
    def _extract_standard_fields(cls, data: Any, envelope: Dict[str, Any]) -> Dict[str, Any]:
        raw_data = cls._safe_dict(data)
        metadata = cls._safe_dict(envelope.get("metadata"))
        user_profile = cls._safe_dict(metadata.get("user_profile"))

        tenant_id = envelope.get("tenant_id") or raw_data.get("tenant_id") or user_profile.get("tenant_id")
        session_id = envelope.get("session_id") or raw_data.get("session_id")
        task_id = envelope.get("task_id") or raw_data.get("task_id")

        message_seq = envelope.get("message_seq")
        if message_seq is None:
            message_seq = raw_data.get("message_seq", 0)

        request_id = envelope.get("request_id") or raw_data.get("request_id")
        envelope_id = envelope.get("envelope_id") or raw_data.get("envelope_id")

        return {
            "tenant_id": tenant_id,
            "session_id": session_id,
            "task_id": task_id,
            "message_seq": int(message_seq or 0),
            "request_id": request_id,
            "envelope_id": envelope_id,
            "metadata": metadata,
        }

    @classmethod
    def create_standardized_envelope(
        cls,
        topic: str,
        data: Any,
        metadata: Optional[dict] = None,
        *,
        tenant_id: Optional[str] = None,
        session_id: Optional[str] = None,
        task_id: Optional[str] = None,
        message_seq: Optional[int] = None,
        request_id: Optional[str] = None,
        envelope_id: Optional[str] = None,
        message_id: Optional[str] = None,
        timestamp: Optional[float] = None,
    ) -> Dict[str, Any]:
        env: Dict[str, Any] = {
            "topic": topic,
            "data": data,
            "timestamp": float(timestamp if timestamp is not None else time.time()),
            "message_id": message_id or str(uuid.uuid4()),
            "metadata": metadata or {},
        }

        extracted = cls._extract_standard_fields(data, env)

        merged = {
            "tenant_id": tenant_id if tenant_id is not None else extracted.get("tenant_id"),
            "session_id": session_id if session_id is not None else extracted.get("session_id"),
            "task_id": task_id if task_id is not None else extracted.get("task_id"),
            "message_seq": int(message_seq if message_seq is not None else extracted.get("message_seq") or 0),
            "request_id": request_id if request_id is not None else extracted.get("request_id"),
            "envelope_id": envelope_id if envelope_id is not None else extracted.get("envelope_id"),
        }

        for k, v in merged.items():
            if v is not None:
                env[k] = v

        return env

    @classmethod
    def envelope_to_processing_context(cls, envelope: Dict[str, Any]) -> Dict[str, Any]:
        topic = envelope.get("topic", "unknown")
        data = envelope.get("data", {})
        extracted = cls._extract_standard_fields(data, envelope)

        # 内存 bus 没有 stream_message_id，用 message_id 代替
        bus_message_id = envelope.get("message_id") or str(uuid.uuid4())
        task_id = extracted.get("task_id") or f"legacy_{bus_message_id}"

        return {
            "envelope": envelope,
            "topic": topic,
            "raw_data": data,
            "metadata": extracted["metadata"],
            "tenant_id": extracted.get("tenant_id"),
            "session_id": extracted.get("session_id"),
            "task_id": task_id,
            "message_seq": extracted.get("message_seq", 0),
            "request_id": extracted.get("request_id"),
            "envelope_id": extracted.get("envelope_id"),
            "bus_message_id": bus_message_id,
        }


# ==========================================================
# 内存队列 BUS（最终版）
# ==========================================================
class MessageBus:
    """
    agent_core/envelope_bus.py（最终版）

    - subscribe(topic, handler): handler(ctx)；ctx 为标准 processing_context
    - publish(topic, data, metadata): 会自动创建标准化 envelope
    - start(): 启动分发循环（async）
    """

    _instance: Optional["MessageBus"] = None

    def __init__(self):
        self.subscribers: Dict[str, List[Handler]] = {}
        self.queue: "asyncio.Queue[Dict[str, Any]]" = asyncio.Queue()
        self.processor = StandardizedMessageProcessor()

        self._running = False
        self._dispatcher_task: Optional[asyncio.Task] = None

    @classmethod
    def get_instance(cls) -> "MessageBus":
        if cls._instance is None:
            cls._instance = MessageBus()
        return cls._instance

    def subscribe(self, topic: str, handler: Handler) -> None:
        """
        注册 handler。handler 入参统一为 processing_context(dict)
        """
        if topic not in self.subscribers:
            self.subscribers[topic] = []
        self.subscribers[topic].append(handler)
        logger.info("✅ Subscribed: topic=%s handlers=%d", topic, len(self.subscribers[topic]))

    async def publish(
        self,
        topic: str,
        data: Any,
        metadata: Optional[dict] = None,
        *,
        tenant_id: Optional[str] = None,
        session_id: Optional[str] = None,
        task_id: Optional[str] = None,
        message_seq: Optional[int] = None,
        request_id: Optional[str] = None,
        envelope_id: Optional[str] = None,
    ) -> str:
        """
        发布消息：写入内存队列
        返回 message_id
        """
        env = self.processor.create_standardized_envelope(
            topic,
            data,
            metadata or {},
            tenant_id=tenant_id,
            session_id=session_id,
            task_id=task_id,
            message_seq=message_seq,
            request_id=request_id,
            envelope_id=envelope_id,
        )
        await self.queue.put(env)

        logger.info(
            "📨 Published: topic=%s tenant=%s session=%s task=%s request=%s envelope=%s msg_id=%s",
            topic,
            env.get("tenant_id", "unknown"),
            env.get("session_id", "unknown"),
            env.get("task_id", "unknown"),
            env.get("request_id", "unknown"),
            env.get("envelope_id", "unknown"),
            env.get("message_id"),
        )
        return env["message_id"]

    async def start(self) -> None:
        """
        启动分发循环（如果你已有主循环，建议 create_task(bus.start())）
        """
        if self._running:
            logger.warning("⚠️ MessageBus already running")
            return

        self._running = True
        self._dispatcher_task = asyncio.create_task(self._dispatch_loop())
        logger.info("🚀 MessageBus started")

    async def stop(self) -> None:
        """
        停止分发循环
        """
        self._running = False
        if self._dispatcher_task:
            self._dispatcher_task.cancel()
            try:
                await self._dispatcher_task
            except asyncio.CancelledError:
                pass
            self._dispatcher_task = None
        logger.info("🛑 MessageBus stopped")

    async def _dispatch_loop(self) -> None:
        while self._running:
            env = await self.queue.get()
            try:
                ctx = self.processor.envelope_to_processing_context(env)
                topic = ctx["topic"]
                handlers = self.subscribers.get(topic, [])

                if not handlers:
                    logger.warning("⚠️ No handlers for topic=%s (msg_id=%s)", topic, ctx.get("bus_message_id"))
                    continue

                # 约定：按注册顺序依次尝试；第一个成功即认为消费成功
                for handler in handlers:
                    try:
                        if asyncio.iscoroutinefunction(handler):
                            await handler(ctx)
                        else:
                            handler(ctx)
                        break
                    except Exception as e:
                        logger.error("❌ Handler failed topic=%s err=%s", topic, e)
                        # 尝试下一个 handler
                        continue
            finally:
                self.queue.task_done()

    def get_bus_stats(self) -> Dict[str, Any]:
        return {
            "type": "memory_bus",
            "running": self._running,
            "topics_registered": list(self.subscribers.keys()),
            "total_handlers": sum(len(v) for v in self.subscribers.values()),
            "queue_size": self.queue.qsize(),
        }
