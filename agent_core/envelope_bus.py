# ai-os/agent_core/envelope_bus.py
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, List, Optional, Union

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

Handler = Union[
    Callable[[Dict[str, Any]], Any],                          # sync handler(ctx)
    Callable[[Dict[str, Any]], Awaitable[Any]],               # async handler(ctx)
]


@dataclass(frozen=True)
class BusMessage:
    """
    Agent Core 内部总线的标准消息结构（建议）
    """
    topic: str
    envelope: Dict[str, Any]
    published_at: float


class MessageBus:
    """
    agent_core 的 in-memory message bus（最终版）

    目标：
    - 标准化 envelope 字段（tenant_id/session_id/task_id/request_id/envelope_id）
    - 支持同步链路：request/response（通过 reply_to + correlation_id）
    - 兼容历史 callback 模式（message["callback"] 可用）
    - 兼容历史 publish/subscribe/start 模式
    """

    _instance: Optional["MessageBus"] = None

    def __init__(self):
        self.subscribers: Dict[str, List[Handler]] = {}
        self.queue: asyncio.Queue[BusMessage] = asyncio.Queue()

        # request/response 等待表：correlation_id -> Future
        self._pending: Dict[str, asyncio.Future] = {}

        self._running: bool = False

    @classmethod
    def get_instance(cls) -> "MessageBus":
        if cls._instance is None:
            cls._instance = MessageBus()
        return cls._instance

    # --------------------------------------------------
    # Subscribe
    # --------------------------------------------------
    def subscribe(self, topic: str, handler: Handler):
        """
        handler(ctx) 形式，ctx 是 processing_context/envelope 的 dict
        """
        if topic not in self.subscribers:
            self.subscribers[topic] = []
        self.subscribers[topic].append(handler)
        logger.info("✅ Subscribed to topic=%s handlers=%d", topic, len(self.subscribers[topic]))

    # --------------------------------------------------
    # Publish
    # --------------------------------------------------
    async def publish(self, topic: str, message: Dict[str, Any]):
        """
        发布消息：message 建议是标准 envelope
        """
        standardized = self._ensure_standard_fields(message)
        await self.queue.put(BusMessage(topic=topic, envelope=standardized, published_at=time.time()))
        logger.debug("📨 Published message topic=%s envelope_id=%s", topic, standardized.get("envelope_id"))

    # --------------------------------------------------
    # Request/Response (同步等待)
    # --------------------------------------------------
    async def request(self, topic: str, message: Dict[str, Any], timeout: float = 30.0) -> Any:
        """
        同步请求：发布到 topic，并等待 reply 返回。

        机制：
        - 自动生成 correlation_id
        - 自动设置 reply_to = "__bus_reply__"
        - 等待 handler 通过 bus.respond(...) 回传，或通过 callback 回传也行（兼容）
        """
        correlation_id = f"corr_{uuid.uuid4().hex}"
        reply_to = "__bus_reply__"

        standardized = self._ensure_standard_fields(message)
        standardized["correlation_id"] = correlation_id
        standardized["reply_to"] = reply_to

        loop = asyncio.get_event_loop()
        fut: asyncio.Future = loop.create_future()
        self._pending[correlation_id] = fut

        # 兼容旧 callback：如果下游用 callback 回传，也能 resolve
        async def _callback(result: Any):
            if not fut.done():
                fut.set_result(result)

        standardized.setdefault("callback", _callback)

        await self.publish(topic, standardized)

        try:
            return await asyncio.wait_for(fut, timeout=timeout)
        finally:
            self._pending.pop(correlation_id, None)

    async def respond(self, correlation_id: str, payload: Any):
        """
        handler 调用：将结果回传给 request()
        """
        fut = self._pending.get(correlation_id)
        if fut and not fut.done():
            fut.set_result(payload)

    # --------------------------------------------------
    # Start Loop
    # --------------------------------------------------
    async def start(self):
        """
        主循环：单协程消费 queue，然后派发给对应 handlers。
        """
        if self._running:
            logger.warning("MessageBus already running")
            return

        self._running = True
        logger.info("🚀 MessageBus started and waiting for messages...")

        while self._running:
            msg: BusMessage = await self.queue.get()
            topic = msg.topic
            envelope = msg.envelope

            handlers = self.subscribers.get(topic, [])
            if not handlers:
                logger.warning("⚠️ No handlers for topic=%s", topic)
                self.queue.task_done()
                continue

            # 逐个 handler 尝试执行：一个成功即认为处理完成
            handled = False
            last_err: Optional[Exception] = None

            for handler in handlers:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        # async handler
                        result = await handler(envelope)
                    else:
                        # sync handler
                        result = handler(envelope)

                    handled = True

                    # 如果是 request 模式，自动回传（当 handler return 非 None 时）
                    correlation_id = envelope.get("correlation_id")
                    reply_to = envelope.get("reply_to")
                    if correlation_id and reply_to == "__bus_reply__" and result is not None:
                        await self.respond(correlation_id, result)

                    break

                except Exception as e:
                    last_err = e
                    logger.exception("❌ Handler error topic=%s err=%s", topic, e)

            if not handled:
                logger.error("❌ All handlers failed topic=%s last_err=%s", topic, last_err)

            self.queue.task_done()

    async def stop(self):
        self._running = False

    # --------------------------------------------------
    # Helpers
    # --------------------------------------------------
    def _ensure_standard_fields(self, envelope: Dict[str, Any]) -> Dict[str, Any]:
        """
        确保 envelope 带齐标准字段（多租户/ABAC 透传一致性）
        """
        if not isinstance(envelope, dict):
            return {"data": envelope}

        data = envelope.get("data", {}) if isinstance(envelope.get("data"), dict) else {}

        # tenant/session/task/request/envelope 的透传优先级：envelope > data > metadata.user_profile
        metadata = envelope.get("metadata", {}) if isinstance(envelope.get("metadata"), dict) else {}
        user_profile = metadata.get("user_profile", {}) if isinstance(metadata.get("user_profile"), dict) else {}

        tenant_id = envelope.get("tenant_id") or data.get("tenant_id") or user_profile.get("tenant_id")
        session_id = envelope.get("session_id") or data.get("session_id")
        task_id = envelope.get("task_id") or data.get("task_id")
        message_seq = envelope.get("message_seq")
        if message_seq is None:
            message_seq = data.get("message_seq", 0)

        request_id = envelope.get("request_id") or data.get("request_id")
        envelope_id = envelope.get("envelope_id") or data.get("envelope_id")

        # 补齐
        if tenant_id is not None:
            envelope["tenant_id"] = tenant_id
        if session_id is not None:
            envelope["session_id"] = session_id
        if task_id is not None:
            envelope["task_id"] = task_id
        envelope["message_seq"] = int(message_seq or 0)

        if request_id is not None:
            envelope["request_id"] = request_id
        if envelope_id is not None:
            envelope["envelope_id"] = envelope_id

        # 默认生成 envelope_id（便于追踪）
        if "envelope_id" not in envelope or not envelope.get("envelope_id"):
            envelope["envelope_id"] = f"env_{uuid.uuid4().hex}"

        # 默认 message_id
        if "message_id" not in envelope or not envelope.get("message_id"):
            envelope["message_id"] = f"msg_{uuid.uuid4().hex}"

        # 默认 timestamp
        if "timestamp" not in envelope:
            envelope["timestamp"] = time.time()

        return envelope
