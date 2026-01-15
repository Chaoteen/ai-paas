# ai-os/agent_core/envelope_bus.py
# FINAL BASELINE (multi-tenant + standardized envelope + sync request/reply)
# - 本地 asyncio Queue 总线（非 Redis）
# - 统一信封结构：topic/data/metadata + session_id/task_id/message_seq + tenant_id/request_id/envelope_id
# - 支持同步 request-reply（不依赖 callback 注入）
# - 向后兼容：publish_legacy(topic, message)

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple, Union


Handler = Union[
    Callable[[Dict[str, Any]], Any],
    Callable[[Dict[str, Any]], Awaitable[Any]],
]


@dataclass(frozen=True)
class StandardEnvelope:
    """
    标准化消息信封（agent_core 内部一致）
    """
    topic: str
    data: Any
    timestamp: float
    message_id: str

    # 标准化 ID
    session_id: Optional[str] = None
    task_id: Optional[str] = None
    message_seq: Optional[int] = None

    # Control Plane 透传字段（用于同步匹配/审计）
    tenant_id: Optional[str] = None
    request_id: Optional[str] = None
    envelope_id: Optional[str] = None

    # 扩展元信息
    metadata: Optional[Dict[str, Any]] = None

    # 同步 request-reply
    correlation_id: Optional[str] = None
    reply_to: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "topic": self.topic,
            "data": self.data,
            "timestamp": self.timestamp,
            "message_id": self.message_id,
            "session_id": self.session_id,
            "task_id": self.task_id,
            "message_seq": self.message_seq,
            "tenant_id": self.tenant_id,
            "request_id": self.request_id,
            "envelope_id": self.envelope_id,
            "metadata": self.metadata or {},
            "correlation_id": self.correlation_id,
            "reply_to": self.reply_to,
        }


class MessageBus:
    """
    本地 MessageBus（升级版）

    设计要点：
    1) 统一信封结构（StandardEnvelope）
    2) 支持同步 request(topic, data, ...) -> await result
       - handler 返回值将自动作为 reply
    3) 多租户字段透传
       - tenant_id/request_id/envelope_id 在 envelope 顶层保留
       - data 内如果也包含同名字段，不做冲突合并（以 envelope 顶层为准）
    """

    _instance: Optional["MessageBus"] = None

    def __init__(self):
        self.subscribers: Dict[str, List[Handler]] = {}
        self.queue: "asyncio.Queue[StandardEnvelope]" = asyncio.Queue()

        # request-reply pending futures
        self._pending: Dict[str, asyncio.Future] = {}
        self._running = False
        self._dispatcher_task: Optional[asyncio.Task] = None

    @classmethod
    def get_instance(cls) -> "MessageBus":
        if cls._instance is None:
            cls._instance = MessageBus()
        return cls._instance

    # -----------------------------
    # Subscribe / Publish
    # -----------------------------

    def subscribe(self, topic: str, handler: Handler) -> None:
        if topic not in self.subscribers:
            self.subscribers[topic] = []
        self.subscribers[topic].append(handler)
        print(f"✅ Subscribed to topic: {topic}")

    async def publish(
        self,
        topic: str,
        data: Any,
        metadata: Optional[Dict[str, Any]] = None,
        *,
        # 标准化 ID（可选）
        session_id: Optional[str] = None,
        task_id: Optional[str] = None,
        message_seq: Optional[int] = None,
        # 多租户/CP 透传（可选）
        tenant_id: Optional[str] = None,
        request_id: Optional[str] = None,
        envelope_id: Optional[str] = None,
        # request-reply（可选）
        correlation_id: Optional[str] = None,
        reply_to: Optional[str] = None,
    ) -> str:
        env = StandardEnvelope(
            topic=topic,
            data=data,
            timestamp=time.time(),
            message_id=str(uuid.uuid4()),
            session_id=session_id,
            task_id=task_id,
            message_seq=message_seq,
            tenant_id=tenant_id,
            request_id=request_id,
            envelope_id=envelope_id,
            metadata=metadata or {},
            correlation_id=correlation_id,
            reply_to=reply_to,
        )
        await self.queue.put(env)
        print(f"📨 Published message to {topic}: {env.message_id}")
        return env.message_id

    # -----------------------------
    # Sync request-reply
    # -----------------------------

    async def request(
        self,
        topic: str,
        data: Any,
        metadata: Optional[Dict[str, Any]] = None,
        *,
        timeout: float = 30.0,
        # 标准化 ID（可选）
        session_id: Optional[str] = None,
        task_id: Optional[str] = None,
        message_seq: Optional[int] = None,
        # 多租户/CP 透传（可选）
        tenant_id: Optional[str] = None,
        request_id: Optional[str] = None,
        envelope_id: Optional[str] = None,
    ) -> Any:
        """
        同步调用：发布请求并等待处理器返回值
        - handler 的返回值会被自动作为 reply
        - 如果 handler 抛异常，会回传异常字符串（并在 request 侧 raise）
        """
        correlation_id = f"corr_{uuid.uuid4().hex}"
        reply_topic = f"__reply__.{correlation_id}"

        loop = asyncio.get_event_loop()
        fut: asyncio.Future = loop.create_future()
        self._pending[correlation_id] = fut

        # reply handler（只处理一次）
        async def _on_reply(env_dict: Dict[str, Any]) -> None:
            try:
                if not fut.done():
                    if env_dict.get("status") == "failed":
                        fut.set_exception(RuntimeError(env_dict.get("error", "UNKNOWN_ERROR")))
                    else:
                        fut.set_result(env_dict.get("result"))
            finally:
                # 清理订阅和 pending
                self._pending.pop(correlation_id, None)
                self._unsubscribe(reply_topic, _on_reply)

        self.subscribe(reply_topic, _on_reply)

        await self.publish(
            topic=topic,
            data=data,
            metadata=metadata,
            session_id=session_id,
            task_id=task_id,
            message_seq=message_seq,
            tenant_id=tenant_id,
            request_id=request_id,
            envelope_id=envelope_id,
            correlation_id=correlation_id,
            reply_to=reply_topic,
        )

        return await asyncio.wait_for(fut, timeout=timeout)

    # -----------------------------
    # Dispatcher loop
    # -----------------------------

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        print("🚀 MessageBus started and waiting for messages...")
        self._dispatcher_task = asyncio.create_task(self._dispatch_loop())

    async def stop(self) -> None:
        self._running = False
        if self._dispatcher_task:
            self._dispatcher_task.cancel()
            try:
                await self._dispatcher_task
            except asyncio.CancelledError:
                pass
            self._dispatcher_task = None

        # 取消所有 pending
        for corr_id, fut in list(self._pending.items()):
            if not fut.done():
                fut.cancel()
            self._pending.pop(corr_id, None)

    async def _dispatch_loop(self) -> None:
        while self._running:
            env: StandardEnvelope = await self.queue.get()
            topic = env.topic
            handlers = self.subscribers.get(topic, [])

            if not handlers:
                # 没有订阅者：如果是 request-reply，回失败
                await self._maybe_reply_failed(env, f"NO_HANDLER_FOR_TOPIC:{topic}")
                continue

            # 逐个 handler 尝试（第一个成功返回即停止）
            handled = False
            last_exc: Optional[BaseException] = None

            for handler in handlers:
                try:
                    env_dict = env.to_dict()

                    if asyncio.iscoroutinefunction(handler):
                        result = await handler(env_dict)
                    else:
                        result = handler(env_dict)

                    # handler 若返回 None：认为已消费但无返回
                    handled = True

                    # request-reply：把返回值回到 reply_to
                    if env.reply_to and env.correlation_id:
                        await self._reply_ok(env, result)

                    break

                except BaseException as e:
                    last_exc = e
                    continue

            if not handled:
                await self._maybe_reply_failed(env, f"HANDLER_FAILED:{last_exc!r}")

    # -----------------------------
    # Reply helpers
    # -----------------------------

    async def _reply_ok(self, req_env: StandardEnvelope, result: Any) -> None:
        await self.publish(
            topic=req_env.reply_to or "__reply__",
            data={
                "status": "completed",
                "result": result,
                "correlation_id": req_env.correlation_id,
            },
            metadata={
                "reply_of": req_env.message_id,
                "topic": req_env.topic,
            },
            # 透传（用于调用方对齐）
            session_id=req_env.session_id,
            task_id=req_env.task_id,
            message_seq=req_env.message_seq,
            tenant_id=req_env.tenant_id,
            request_id=req_env.request_id,
            envelope_id=req_env.envelope_id,
        )

    async def _maybe_reply_failed(self, req_env: StandardEnvelope, error: str) -> None:
        if not req_env.reply_to or not req_env.correlation_id:
            return
        await self.publish(
            topic=req_env.reply_to,
            data={
                "status": "failed",
                "error": error,
                "correlation_id": req_env.correlation_id,
            },
            metadata={
                "reply_of": req_env.message_id,
                "topic": req_env.topic,
            },
            session_id=req_env.session_id,
            task_id=req_env.task_id,
            message_seq=req_env.message_seq,
            tenant_id=req_env.tenant_id,
            request_id=req_env.request_id,
            envelope_id=req_env.envelope_id,
        )

    # -----------------------------
    # Internal utils
    # -----------------------------

    def _unsubscribe(self, topic: str, handler: Handler) -> None:
        handlers = self.subscribers.get(topic, [])
        try:
            handlers.remove(handler)
        except ValueError:
            return
        if not handlers:
            self.subscribers.pop(topic, None)

    # -----------------------------
    # Backward compatibility
    # -----------------------------

    async def publish_legacy(self, topic: str, message: Any) -> str:
        """
        旧接口兼容：只传 message，不传 metadata/tenant 等
        """
        return await self.publish(topic=topic, data=message, metadata={})


# 兼容旧引用（你老代码里叫 MessageBus）
__all__ = ["MessageBus", "StandardEnvelope"]
