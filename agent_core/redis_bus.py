# ai-os/agent_core/redis_bus.py
from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
import uuid
from concurrent.futures import TimeoutError as FuturesTimeoutError
from typing import Any, Callable, Dict, List, Optional

import redis

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


# ==========================================================
# 标准化 Envelope / Context 处理
# ==========================================================
class StandardizedMessageProcessor:
    """
    约定的标准化消息 envelope：
    {
      "topic": "...",
      "data": {...},
      "timestamp": ...,
      "message_id": "...",
      "session_id": "...",
      "task_id": "...",
      "message_seq": ...,
      "request_id": "...",      # Control Plane 透传
      "envelope_id": "...",     # Control Plane 透传
      "tenant_id": "...",       # 多租户
      "metadata": {...}
    }
    """

    @staticmethod
    def _extract_standard_fields(data: Any, envelope: Dict[str, Any]) -> Dict[str, Any]:
        """
        从 envelope / data / metadata 多路提取标准字段
        """
        raw_data = data if isinstance(data, dict) else {}
        metadata = envelope.get("metadata", {}) if isinstance(envelope.get("metadata"), dict) else {}

        # tenant_id 优先级：envelope > data > metadata.user_profile.tenant_id
        tenant_id = (
            envelope.get("tenant_id")
            or raw_data.get("tenant_id")
            or (metadata.get("user_profile", {}) or {}).get("tenant_id")
        )

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
    def create_standardized_envelope(cls, topic: str, data: Any, metadata: Optional[dict] = None) -> dict:
        """
        发布时统一封装，保证 downstream 能拿到 tenant/session/task/request/envelope 等字段
        """
        if metadata is None:
            metadata = {}

        envelope = {
            "topic": topic,
            "data": data,
            "timestamp": time.time(),
            "message_id": str(uuid.uuid4()),
            "metadata": metadata or {},
        }

        # 尽量从 data / metadata 中补齐标准字段
        extracted = cls._extract_standard_fields(data, envelope)
        for k in ("tenant_id", "session_id", "task_id", "message_seq", "request_id", "envelope_id"):
            if extracted.get(k) is not None:
                envelope[k] = extracted[k]

        return envelope

    @classmethod
    def parse_message_to_context(cls, raw_message: str, message_id: str) -> dict:
        """
        将 stream 中的 message(json string) 转换为 processing_context
        """
        try:
            envelope = json.loads(raw_message)
            if not isinstance(envelope, dict):
                raise ValueError("Envelope is not a dict")

            data = envelope.get("data", {})
            extracted = cls._extract_standard_fields(data, envelope)

            processing_context = {
                "envelope": envelope,
                "topic": envelope.get("topic", "unknown"),
                "raw_data": data if isinstance(data, dict) else data,
                "metadata": extracted["metadata"],
                # 标准字段（强烈建议下游使用这些）
                "tenant_id": extracted["tenant_id"],
                "session_id": extracted["session_id"],
                "task_id": extracted["task_id"] or f"legacy_{message_id}",
                "message_seq": extracted["message_seq"],
                "request_id": extracted["request_id"],
                "envelope_id": extracted["envelope_id"],
                # stream 级别字段
                "stream_message_id": message_id,
            }
            return processing_context

        except Exception as e:
            logger.error("❌ 解析消息失败: %s", e)
            # 回退：仍返回一个可处理的 context
            return {
                "envelope": {"topic": "unknown", "data": raw_message, "metadata": {}},
                "topic": "unknown",
                "raw_data": raw_message,
                "metadata": {},
                "tenant_id": None,
                "session_id": None,
                "task_id": f"legacy_{message_id}",
                "message_seq": 0,
                "request_id": None,
                "envelope_id": None,
                "stream_message_id": message_id,
            }

    @staticmethod
    def is_legacy_format(data: Any) -> bool:
        """
        旧格式：非 dict 或缺少关键字段
        """
        if not isinstance(data, dict):
            return True
        return not ("task_id" in data or "session_id" in data or "tenant_id" in data)


# ==========================================================
# 幂等去重：tenant_id:session_id:task_id
# ==========================================================
class MessageDeduplicator:
    def __init__(self, redis_client: redis.Redis, key_prefix: str = "dedup:"):
        self.redis = redis_client
        self.key_prefix = key_prefix
        logger.info("✅ MessageDeduplicator初始化完成 - 前缀: %s", key_prefix)

    def _dedup_key(self, ctx: dict) -> str:
        tenant_id = ctx.get("tenant_id") or "tenant_unknown"
        session_id = ctx.get("session_id") or "session_unknown"
        task_id = ctx.get("task_id") or "task_unknown"
        # tenant 隔离是关键
        return f"{tenant_id}:{session_id}:{task_id}"

    def is_duplicate_task(self, ctx: dict, expire_seconds: int = 300) -> bool:
        """
        SETNX：第一次 seen 返回 False；后续返回 True
        """
        dkey = self._dedup_key(ctx)
        key = f"{self.key_prefix}task:{dkey}"

        try:
            is_new = self.redis.setnx(key, "1")
            if is_new:
                self.redis.expire(key, expire_seconds)
                logger.debug("🆕 新任务: %s", dkey)
                return False
            logger.warning("🔄 重复任务: %s", dkey)
            return True
        except Exception as e:
            logger.error("❌ 幂等检查失败: %s", e)
            # 出错时按“非重复”处理，避免误杀
            return False

    def mark_task_processed(self, ctx: dict, expire_seconds: int = 300) -> None:
        dkey = self._dedup_key(ctx)
        key = f"{self.key_prefix}task:{dkey}"
        try:
            self.redis.setex(key, expire_seconds, "processed")
        except Exception as e:
            logger.error("❌ 标记处理完成失败: %s", e)


# ==========================================================
# Redis Stream BUS（最终版）
# ==========================================================
class RedisBackedEnvelopeBUS:
    """
    标准化 Redis Streams BUS（最终版）

    - subscribe(topic, handler): handler 接收 processing_context
    - publish(topic, data, metadata): data 可 dict/any，metadata dict
    """

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379",
        stream_name: str = "agent.tasks.stream",
        consumer_group: str = "task_manager_workers",
        consumer_id: Optional[str] = None,
        enable_deduplication: bool = True,
        dedup_expire_seconds: int = 300,
        block_ms: int = 5000,
        read_count: int = 10,
        handler_timeout_seconds: int = 30,
        auto_ack_on_error: bool = False,  # 默认不要：失败应留在 pending 便于排查/重试
    ):
        self.redis_url = redis_url
        self.stream_name = stream_name
        self.consumer_group = consumer_group
        self.consumer_id = consumer_id or f"consumer_{uuid.uuid4().hex[:8]}"

        self.redis = redis.Redis.from_url(redis_url, decode_responses=True)
        self.local_handlers: Dict[str, List[Callable]] = {}

        self.enable_deduplication = enable_deduplication
        self.dedup_expire_seconds = dedup_expire_seconds
        self.deduplicator = MessageDeduplicator(self.redis) if enable_deduplication else None

        self.message_processor = StandardizedMessageProcessor()

        self._running = False
        self._listening_thread: Optional[threading.Thread] = None
        self._main_loop: Optional[asyncio.AbstractEventLoop] = None

        # 读取参数
        self.block_ms = block_ms
        self.read_count = read_count
        self.handler_timeout_seconds = handler_timeout_seconds
        self.auto_ack_on_error = auto_ack_on_error

        self._initialize_stream_group()
        logger.info(
            "✅ RedisBackedEnvelopeBUS初始化完成 - stream=%s group=%s consumer=%s",
            stream_name,
            consumer_group,
            self.consumer_id,
        )

    # --------------------------
    # Streams group init
    # --------------------------
    def _initialize_stream_group(self):
        try:
            self.redis.xgroup_create(
                name=self.stream_name,
                groupname=self.consumer_group,
                id="0",
                mkstream=True,
            )
            logger.info("✅ 创建Stream消费者组: %s", self.consumer_group)
        except Exception as e:
            if "BUSYGROUP" in str(e):
                logger.info("✅ Stream消费者组已存在: %s", self.consumer_group)
            else:
                logger.error("❌ 初始化Stream消费者组失败: %s", e)
                raise

    # --------------------------
    # Subscribe / Publish
    # --------------------------
    async def subscribe(self, topic: str, handler: Callable):
        if topic not in self.local_handlers:
            self.local_handlers[topic] = []
        self.local_handlers[topic].append(handler)
        logger.info("✅ 订阅topic: %s handlers=%d", topic, len(self.local_handlers[topic]))

    async def publish(
        self,
        topic: str,
        data: Any,
        metadata: Optional[dict] = None,
    ):
        """
        统一 publish：写入 stream_name
        """
        try:
            env = self.message_processor.create_standardized_envelope(topic, data, metadata or {})
            message_str = json.dumps(env, ensure_ascii=False)

            mid = self.redis.xadd(
                self.stream_name,
                {"message": message_str},
                maxlen=10000,
            )

            logger.info(
                "📨 发布消息 stream=%s id=%s tenant=%s session=%s task=%s topic=%s",
                self.stream_name,
                mid,
                env.get("tenant_id", "unknown"),
                env.get("session_id", "unknown"),
                env.get("task_id", "unknown"),
                topic,
            )
            return mid
        except Exception as e:
            logger.error("❌ 发布失败 stream=%s topic=%s err=%s", self.stream_name, topic, e)
            raise

    async def publish_standardized(self, topic: str, processing_context: dict):
        """
        专用：直接将 processing_context 的 envelope/raw_data/metadata 合成发布
        """
        envelope = processing_context.get("envelope", {}) if isinstance(processing_context.get("envelope"), dict) else {}
        data = envelope.get("data", processing_context.get("raw_data"))
        metadata = processing_context.get("metadata", {})
        return await self.publish(topic, data, metadata)

    # --------------------------
    # Start / Stop
    # --------------------------
    async def start(self):
        """
        在主事件循环调用
        """
        self._main_loop = asyncio.get_event_loop()
        self._running = True

        if self._listening_thread is None:
            self._listening_thread = threading.Thread(
                target=self._stream_message_handler,
                daemon=True,
                name="RedisBackedEnvelopeBUS",
            )
            self._listening_thread.start()
            logger.info("🚀 RedisBackedEnvelopeBUS Streams监听线程已启动")

    async def stop(self):
        self._running = False
        logger.info("🛑 停止RedisBackedEnvelopeBUS ...")

        if self._listening_thread and self._listening_thread.is_alive():
            try:
                self._listening_thread.join(timeout=3.0)
            except Exception as e:
                logger.warning("⚠️ join线程警告: %s", e)

        logger.info("🛑 RedisBackedEnvelopeBUS已停止")

    # --------------------------
    # Stream loop
    # --------------------------
    def _stream_message_handler(self):
        """
        后台线程：xreadgroup -> parse -> (dedup) -> dispatch -> ack
        """
        logger.info("🟢 Streams线程启动 consumer=%s", self.consumer_id)

        while self._running:
            try:
                messages = self.redis.xreadgroup(
                    groupname=self.consumer_group,
                    consumername=self.consumer_id,
                    streams={self.stream_name: ">"},
                    count=self.read_count,
                    block=self.block_ms,
                )

                if not messages:
                    continue

                for _stream, msg_list in messages:
                    for msg_id, msg_data in msg_list:
                        try:
                            raw = msg_data.get("message", "")
                            if not raw:
                                logger.warning("⚠️ message字段缺失 msg_id=%s data=%s", msg_id, msg_data)
                                # 没法处理：直接 ack 避免卡住
                                self.redis.xack(self.stream_name, self.consumer_group, msg_id)
                                continue

                            ctx = self.message_processor.parse_message_to_context(raw, msg_id)
                            topic = ctx.get("topic", "unknown")

                            logger.info(
                                "📨 收到消息 id=%s topic=%s tenant=%s session=%s task=%s",
                                msg_id,
                                topic,
                                ctx.get("tenant_id", "unknown"),
                                ctx.get("session_id", "unknown"),
                                ctx.get("task_id", "unknown"),
                            )

                            # 幂等去重（tenant隔离）
                            if self.enable_deduplication and self.deduplicator:
                                if self.deduplicator.is_duplicate_task(ctx, expire_seconds=self.dedup_expire_seconds):
                                    # 重复任务：直接 ack
                                    self.redis.xack(self.stream_name, self.consumer_group, msg_id)
                                    continue

                            handlers = self.local_handlers.get(topic, [])
                            if not handlers:
                                logger.warning("⚠️ 无handler topic=%s，直接ack避免堆积", topic)
                                self.redis.xack(self.stream_name, self.consumer_group, msg_id)
                                continue

                            # 调用 handler：只要一个成功就算成功（你原逻辑也是 break）
                            success = False
                            last_err: Optional[Exception] = None

                            for handler in handlers:
                                try:
                                    if asyncio.iscoroutinefunction(handler):
                                        if not self._main_loop or not self._main_loop.is_running():
                                            raise RuntimeError("主事件循环不可用，无法调度async handler")

                                        fut = asyncio.run_coroutine_threadsafe(handler(ctx), self._main_loop)
                                        fut.result(timeout=self.handler_timeout_seconds)
                                    else:
                                        handler(ctx)

                                    success = True
                                    break

                                except FuturesTimeoutError as e:
                                    # 线程等待超时：通常 handler 仍可能在跑，按成功处理避免重复消费
                                    logger.warning("⚠️ handler超时(按成功处理) topic=%s err=%s", topic, e)
                                    success = True
                                    break
                                except Exception as e:
                                    last_err = e
                                    logger.error("❌ handler失败 topic=%s err=%s", topic, e)
                                    # 尝试下一个 handler

                            if success:
                                self.redis.xack(self.stream_name, self.consumer_group, msg_id)
                                if self.enable_deduplication and self.deduplicator:
                                    self.deduplicator.mark_task_processed(ctx, expire_seconds=self.dedup_expire_seconds)
                                logger.info("✅ ack完成 msg_id=%s", msg_id)
                            else:
                                logger.error("❌ 所有handler失败 msg_id=%s topic=%s last_err=%s", msg_id, topic, last_err)
                                if self.auto_ack_on_error:
                                    self.redis.xack(self.stream_name, self.consumer_group, msg_id)
                                    logger.warning("⚠️ auto_ack_on_error=True，已ack失败消息 msg_id=%s", msg_id)

                        except Exception as e:
                            logger.error("❌ 消息处理异常 msg_id=%s err=%s", msg_id, e)
                            # 这里不要 ack：保留 pending 便于排查
                            if self.auto_ack_on_error:
                                self.redis.xack(self.stream_name, self.consumer_group, msg_id)
                                logger.warning("⚠️ auto_ack_on_error=True，异常消息已ack msg_id=%s", msg_id)

            except Exception as e:
                if "NOGROUP" in str(e):
                    logger.warning("🔄 NOGROUP，重新初始化消费者组...")
                    try:
                        self._initialize_stream_group()
                    except Exception as inner:
                        logger.error("❌ 重新初始化失败: %s", inner)
                else:
                    logger.error("❌ Streams循环异常: %s", e)

                time.sleep(1)

        logger.info("🛑 Streams线程退出 consumer=%s", self.consumer_id)

    # --------------------------
    # Stats
    # --------------------------
    def get_bus_stats(self) -> Dict[str, Any]:
        return {
            "stream_name": self.stream_name,
            "consumer_group": self.consumer_group,
            "consumer_id": self.consumer_id,
            "topics_registered": list(self.local_handlers.keys()),
            "total_handlers": sum(len(v) for v in self.local_handlers.values()),
            "deduplication": {
                "enabled": self.enable_deduplication,
                "key": "tenant_id:session_id:task_id",
                "expire_seconds": self.dedup_expire_seconds,
            },
            "running": self._running,
        }


def create_message_bus(
    use_redis: bool = True,
    redis_url: str = "redis://localhost:6379",
    stream_name: str = "agent.tasks.stream",
    consumer_group: str = "task_manager_workers",
    enable_deduplication: bool = True,
) -> Any:
    """
    工厂函数：保持你原来调用习惯
    """
    if not use_redis:
        # 你如果还需要本地 bus，可在这里回退；当前默认只返回 redis bus
        raise RuntimeError("use_redis=False not supported in this final version")

    return RedisBackedEnvelopeBUS(
        redis_url=redis_url,
        stream_name=stream_name,
        consumer_group=consumer_group,
        enable_deduplication=enable_deduplication,
    )
