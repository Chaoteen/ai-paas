# ai-os/agent_core/redis_bus.py
from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
import uuid
from concurrent.futures import TimeoutError as FuturesTimeoutError
from typing import Any, Callable, Dict, List, Optional, Tuple

import redis

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


# ==========================================================
# 标准化 Envelope / Context 处理（最终版）
# ==========================================================
class StandardizedMessageProcessor:
    """
    约定标准化消息 envelope（最终版）:

    {
      "topic": "...",
      "data": {...},
      "timestamp": ...,
      "message_id": "...",

      # 标准追踪/多租户字段（必须尽可能透传）
      "tenant_id": "...",
      "session_id": "...",
      "task_id": "...",
      "message_seq": ...,
      "request_id": "...",      # Control Plane 透传
      "envelope_id": "...",     # Control Plane 透传

      # 只读扩展
      "metadata": {...}
    }

    处理原则：
    - redis_bus 不做授权/策略裁决（那是 Control Plane）
    - redis_bus 必须保证 tenant_id/request_id/envelope_id 透传不丢
    - 解析失败要返回可处理的 processing_context（降级）
    """

    @staticmethod
    def _safe_dict(x: Any) -> Dict[str, Any]:
        return x if isinstance(x, dict) else {}

    @classmethod
    def _extract_standard_fields(cls, data: Any, envelope: Dict[str, Any]) -> Dict[str, Any]:
        raw_data = cls._safe_dict(data)
        metadata = cls._safe_dict(envelope.get("metadata"))

        user_profile = cls._safe_dict(metadata.get("user_profile"))
        # tenant_id 优先级：envelope > data > metadata.user_profile
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
        """
        发布时统一封装：允许调用方显式传入标准字段（优先级高于 data/metadata 自动提取）
        """
        env: Dict[str, Any] = {
            "topic": topic,
            "data": data,
            "timestamp": float(timestamp if timestamp is not None else time.time()),
            "message_id": message_id or str(uuid.uuid4()),
            "metadata": metadata or {},
        }

        extracted = cls._extract_standard_fields(data, env)

        # 显式字段优先，其次 extracted
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
    def parse_message_to_context(cls, raw_message: str, stream_message_id: str) -> Dict[str, Any]:
        """
        将 stream 中 message(json string) 转换为 processing_context
        """
        try:
            envelope = json.loads(raw_message)
            if not isinstance(envelope, dict):
                raise ValueError("Envelope is not a dict")

            topic = envelope.get("topic", "unknown")
            data = envelope.get("data", {})
            extracted = cls._extract_standard_fields(data, envelope)

            task_id = extracted.get("task_id") or f"legacy_{stream_message_id}"

            return {
                # 原始
                "envelope": envelope,
                "topic": topic,
                "raw_data": data,
                "metadata": extracted["metadata"],
                # 标准字段
                "tenant_id": extracted.get("tenant_id"),
                "session_id": extracted.get("session_id"),
                "task_id": task_id,
                "message_seq": extracted.get("message_seq", 0),
                "request_id": extracted.get("request_id"),
                "envelope_id": extracted.get("envelope_id"),
                # stream 级字段
                "stream_message_id": stream_message_id,
            }

        except Exception as e:
            logger.error("❌ 解析消息失败: %s", e)
            return {
                "envelope": {"topic": "unknown", "data": raw_message, "metadata": {}},
                "topic": "unknown",
                "raw_data": raw_message,
                "metadata": {},
                "tenant_id": None,
                "session_id": None,
                "task_id": f"legacy_{stream_message_id}",
                "message_seq": 0,
                "request_id": None,
                "envelope_id": None,
                "stream_message_id": stream_message_id,
            }

    @staticmethod
    def is_legacy_format(data: Any) -> bool:
        if not isinstance(data, dict):
            return True
        return not ("task_id" in data or "session_id" in data or "tenant_id" in data)


# ==========================================================
# 幂等去重：tenant_id:session_id:task_id（最终版）
# ==========================================================
class MessageDeduplicator:
    """
    幂等去重必须 tenant 隔离：
    - dedup key = tenant_id:session_id:task_id
    - 可选：如果 task_id 不稳定，也可在上游让 task_id=control_plane.request_id
    """

    def __init__(self, redis_client: redis.Redis, key_prefix: str = "dedup:"):
        self.redis = redis_client
        self.key_prefix = key_prefix
        logger.info("✅ MessageDeduplicator初始化完成 - 前缀: %s", key_prefix)

    def _dedup_key(self, ctx: dict) -> str:
        tenant_id = ctx.get("tenant_id") or "tenant_unknown"
        session_id = ctx.get("session_id") or "session_unknown"
        task_id = ctx.get("task_id") or "task_unknown"
        return f"{tenant_id}:{session_id}:{task_id}"

    def is_duplicate_task(self, ctx: dict, expire_seconds: int = 300) -> bool:
        dkey = self._dedup_key(ctx)
        key = f"{self.key_prefix}task:{dkey}"

        try:
            is_new = self.redis.setnx(key, "1")
            if is_new:
                self.redis.expire(key, expire_seconds)
                return False
            logger.warning("🔄 重复任务: %s", dkey)
            return True
        except Exception as e:
            logger.error("❌ 幂等检查失败: %s", e)
            return False  # 出错按“非重复”处理，避免误杀

    def mark_task_processed(self, ctx: dict, expire_seconds: int = 300) -> None:
        dkey = self._dedup_key(ctx)
        key = f"{self.key_prefix}task:{dkey}"
        try:
            self.redis.setex(key, expire_seconds, "processed")
        except Exception as e:
            logger.error("❌ 标记处理完成失败: %s", e)


# ==========================================================
# Redis Stream BUS（最终版：多租户/可恢复/可观察）
# ==========================================================
class RedisBackedEnvelopeBUS:
    """
    标准化 Redis Streams BUS（最终版）

    核心接口：
    - subscribe(topic, handler): handler(ctx) 其中 ctx 是 processing_context
    - publish(topic, data, metadata): 自动封装标准 envelope 并写入 stream

    多租户策略：
    - 默认：所有租户共享一个 stream（靠 tenant_id 字段隔离）
    - 可选：按租户分 stream（stream_partition_mode="per_tenant"）

    稳定性策略：
    - 默认失败不 ack（留在 pending 便于排查/重试）
    - 支持 xautoclaim 抢占“卡住的 pending”（可选启用）
    """

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379",
        stream_name: str = "agent.tasks.stream",
        consumer_group: str = "task_manager_workers",
        consumer_id: Optional[str] = None,
        *,
        enable_deduplication: bool = True,
        dedup_expire_seconds: int = 300,
        block_ms: int = 5000,
        read_count: int = 10,
        handler_timeout_seconds: int = 30,
        auto_ack_on_error: bool = False,  # 默认 False：失败留 pending
        # 多租户分区
        stream_partition_mode: str = "shared",  # "shared" | "per_tenant"
        stream_name_template: str = "{base}:{tenant_id}",  # per_tenant 时生效
        # pending 恢复
        enable_pending_recovery: bool = True,
        pending_idle_ms: int = 60000,  # 1min idle 视为可抢占
        pending_batch: int = 50,
        # DLQ
        enable_dlq: bool = True,
        dlq_stream_name: str = "agent.dlq.stream",
    ):
        self.redis_url = redis_url
        self.base_stream_name = stream_name
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

        self.block_ms = int(block_ms)
        self.read_count = int(read_count)
        self.handler_timeout_seconds = int(handler_timeout_seconds)
        self.auto_ack_on_error = bool(auto_ack_on_error)

        self.stream_partition_mode = stream_partition_mode
        self.stream_name_template = stream_name_template

        self.enable_pending_recovery = bool(enable_pending_recovery)
        self.pending_idle_ms = int(pending_idle_ms)
        self.pending_batch = int(pending_batch)

        self.enable_dlq = bool(enable_dlq)
        self.dlq_stream_name = dlq_stream_name

        # shared stream 初始化 group
        self._initialize_stream_group(self.base_stream_name)

        logger.info(
            "✅ RedisBackedEnvelopeBUS初始化完成 - mode=%s base_stream=%s group=%s consumer=%s",
            self.stream_partition_mode,
            self.base_stream_name,
            self.consumer_group,
            self.consumer_id,
        )

    # --------------------------
    # Stream helpers
    # --------------------------
    def _resolve_stream_name(self, tenant_id: Optional[str]) -> str:
        if self.stream_partition_mode == "per_tenant":
            tid = tenant_id or "tenant_unknown"
            return self.stream_name_template.format(base=self.base_stream_name, tenant_id=tid)
        return self.base_stream_name

    def _initialize_stream_group(self, stream_name: str):
        try:
            self.redis.xgroup_create(name=stream_name, groupname=self.consumer_group, id="0", mkstream=True)
            logger.info("✅ 创建Stream消费者组: stream=%s group=%s", stream_name, self.consumer_group)
        except Exception as e:
            if "BUSYGROUP" in str(e):
                logger.info("✅ Stream消费者组已存在: stream=%s group=%s", stream_name, self.consumer_group)
            else:
                logger.error("❌ 初始化Stream消费者组失败: stream=%s err=%s", stream_name, e)
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
        *,
        # 允许显式透传 Control Plane 字段（优先级最高）
        tenant_id: Optional[str] = None,
        session_id: Optional[str] = None,
        task_id: Optional[str] = None,
        message_seq: Optional[int] = None,
        request_id: Optional[str] = None,
        envelope_id: Optional[str] = None,
    ):
        """
        统一 publish：写入（shared 或 per_tenant）stream
        """
        env = self.message_processor.create_standardized_envelope(
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

        resolved_stream = self._resolve_stream_name(env.get("tenant_id"))
        if self.stream_partition_mode == "per_tenant":
            # per-tenant stream 需要确保 group 存在
            self._initialize_stream_group(resolved_stream)

        try:
            message_str = json.dumps(env, ensure_ascii=False)
            mid = self.redis.xadd(resolved_stream, {"message": message_str}, maxlen=10000)

            logger.info(
                "📨 发布消息 stream=%s id=%s tenant=%s session=%s task=%s request=%s topic=%s",
                resolved_stream,
                mid,
                env.get("tenant_id", "unknown"),
                env.get("session_id", "unknown"),
                env.get("task_id", "unknown"),
                env.get("request_id", "unknown"),
                topic,
            )
            return mid
        except Exception as e:
            logger.error("❌ 发布失败 stream=%s topic=%s err=%s", resolved_stream, topic, e)
            raise

    async def publish_standardized(self, topic: str, processing_context: dict):
        envelope = processing_context.get("envelope", {}) if isinstance(processing_context.get("envelope"), dict) else {}
        data = envelope.get("data", processing_context.get("raw_data"))
        metadata = processing_context.get("metadata", {})
        return await self.publish(
            topic,
            data,
            metadata,
            tenant_id=processing_context.get("tenant_id"),
            session_id=processing_context.get("session_id"),
            task_id=processing_context.get("task_id"),
            message_seq=processing_context.get("message_seq"),
            request_id=processing_context.get("request_id"),
            envelope_id=processing_context.get("envelope_id"),
        )

    # --------------------------
    # Start / Stop
    # --------------------------
    async def start(self):
        self._main_loop = asyncio.get_event_loop()
        self._running = True

        if self._listening_thread is None:
            self._listening_thread = threading.Thread(
                target=self._stream_loop,
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
    # Pending recovery
    # --------------------------
    def _try_recover_pending(self, stream_name: str) -> List[Tuple[str, Dict[str, Any]]]:
        """
        使用 XAUTOCLAIM 抢占 idle 超过 pending_idle_ms 的 pending 消息
        返回 [(msg_id, msg_data), ...]
        """
        if not self.enable_pending_recovery:
            return []
        try:
            # redis-py 对 xautoclaim 的签名在不同版本可能略有差异，这里用 execute_command 兼容
            # XAUTOCLAIM <key> <group> <consumer> <min-idle-time> <start> [COUNT <count>]
            resp = self.redis.execute_command(
                "XAUTOCLAIM",
                stream_name,
                self.consumer_group,
                self.consumer_id,
                self.pending_idle_ms,
                "0-0",
                "COUNT",
                self.pending_batch,
            )
            # resp: [next_start_id, [[msg_id, {field: value}],[...]], deleted_ids]
            if not resp or len(resp) < 2:
                return []
            claimed = resp[1] or []
            out: List[Tuple[str, Dict[str, Any]]] = []
            for item in claimed:
                if isinstance(item, (list, tuple)) and len(item) == 2:
                    out.append((item[0], item[1]))
            if out:
                logger.warning("🔁 抢占pending消息 stream=%s count=%d", stream_name, len(out))
            return out
        except Exception as e:
            # 不影响主循环
            logger.debug("pending recovery skipped: %s", e)
            return []

    # --------------------------
    # DLQ
    # --------------------------
    def _push_dlq(self, stream_name: str, msg_id: str, raw_message: str, error: str):
        if not self.enable_dlq:
            return
        try:
            dlq_payload = {
                "source_stream": stream_name,
                "source_message_id": msg_id,
                "error": error,
                "timestamp": time.time(),
                "raw": raw_message,
            }
            self.redis.xadd(self.dlq_stream_name, {"message": json.dumps(dlq_payload, ensure_ascii=False)}, maxlen=20000)
        except Exception as e:
            logger.error("❌ 写入DLQ失败: %s", e)

    # --------------------------
    # Stream loop
    # --------------------------
    def _stream_loop(self):
        """
        后台线程：xreadgroup -> parse -> dedup -> dispatch -> ack
        + 可选 pending recovery
        """
        logger.info("🟢 Streams线程启动 consumer=%s", self.consumer_id)

        while self._running:
            # 目前只监听 base_stream；如果你启用 per_tenant 分区并希望“自动发现租户 stream”，
            # 需要额外维护租户列表。最终版默认由发布方选择 stream（本 bus 不做租户枚举）。
            stream_name = self.base_stream_name

            try:
                # 先尝试抢占 pending
                claimed = self._try_recover_pending(stream_name)
                if claimed:
                    for msg_id, msg_data in claimed:
                        self._handle_one(stream_name, msg_id, msg_data, from_pending=True)

                # 再读新消息
                messages = self.redis.xreadgroup(
                    groupname=self.consumer_group,
                    consumername=self.consumer_id,
                    streams={stream_name: ">"},
                    count=self.read_count,
                    block=self.block_ms,
                )

                if not messages:
                    continue

                for _stream, msg_list in messages:
                    for msg_id, msg_data in msg_list:
                        self._handle_one(stream_name, msg_id, msg_data, from_pending=False)

            except Exception as e:
                if "NOGROUP" in str(e):
                    logger.warning("🔄 NOGROUP,重新初始化消费者组... stream=%s", stream_name)
                    try:
                        self._initialize_stream_group(stream_name)
                    except Exception as inner:
                        logger.error("❌ 重新初始化失败: %s", inner)
                else:
                    logger.error("❌ Streams循环异常: %s", e)

                time.sleep(1)

        logger.info("🛑 Streams线程退出 consumer=%s", self.consumer_id)

    def _handle_one(self, stream_name: str, msg_id: str, msg_data: Dict[str, Any], *, from_pending: bool):
        """
        处理单条消息（线程内）
        """
        raw = msg_data.get("message", "")
        if not raw:
            logger.warning("⚠️ message字段缺失 msg_id=%s data=%s", msg_id, msg_data)
            self.redis.xack(stream_name, self.consumer_group, msg_id)
            return

        try:
            ctx = self.message_processor.parse_message_to_context(raw, msg_id)
            topic = ctx.get("topic", "unknown")

            logger.info(
                "📨 收到消息%s id=%s topic=%s tenant=%s session=%s task=%s request=%s",
                " (PENDING)" if from_pending else "",
                msg_id,
                topic,
                ctx.get("tenant_id", "unknown"),
                ctx.get("session_id", "unknown"),
                ctx.get("task_id", "unknown"),
                ctx.get("request_id", "unknown"),
            )

            # 多租户关键：tenant_id 缺失要显著告警（但不强制丢弃，避免误杀 legacy）
            if not ctx.get("tenant_id"):
                logger.warning("⚠️ tenant_id缺失（可能是legacy消息） msg_id=%s topic=%s", msg_id, topic)

            # 幂等去重（tenant隔离）
            if self.enable_deduplication and self.deduplicator:
                if self.deduplicator.is_duplicate_task(ctx, expire_seconds=self.dedup_expire_seconds):
                    self.redis.xack(stream_name, self.consumer_group, msg_id)
                    return

            handlers = self.local_handlers.get(topic, [])
            if not handlers:
                logger.warning("⚠️ 无handler topic=%s,直接ack避免堆积", topic)
                self.redis.xack(stream_name, self.consumer_group, msg_id)
                return

            success = False
            last_err: Optional[Exception] = None

            for handler in handlers:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        if not self._main_loop or not self._main_loop.is_running():
                            raise RuntimeError("主事件循环不可用,无法调度async handler")

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

            if success:
                self.redis.xack(stream_name, self.consumer_group, msg_id)
                if self.enable_deduplication and self.deduplicator:
                    self.deduplicator.mark_task_processed(ctx, expire_seconds=self.dedup_expire_seconds)
                logger.info("✅ ack完成 msg_id=%s", msg_id)
            else:
                err_str = str(last_err) if last_err else "unknown_handler_error"
                logger.error("❌ 所有handler失败 msg_id=%s topic=%s last_err=%s", msg_id, topic, err_str)
                self._push_dlq(stream_name, msg_id, raw, err_str)
                if self.auto_ack_on_error:
                    self.redis.xack(stream_name, self.consumer_group, msg_id)
                    logger.warning("⚠️ auto_ack_on_error=True，已ack失败消息 msg_id=%s", msg_id)

        except Exception as e:
            logger.error("❌ 消息处理异常 msg_id=%s err=%s", msg_id, e)
            self._push_dlq(stream_name, msg_id, raw, f"exception:{e}")
            if self.auto_ack_on_error:
                self.redis.xack(stream_name, self.consumer_group, msg_id)
                logger.warning("⚠️ auto_ack_on_error=True，异常消息已ack msg_id=%s", msg_id)

    # --------------------------
    # Stats
    # --------------------------
    def get_bus_stats(self) -> Dict[str, Any]:
        return {
            "base_stream_name": self.base_stream_name,
            "consumer_group": self.consumer_group,
            "consumer_id": self.consumer_id,
            "topics_registered": list(self.local_handlers.keys()),
            "total_handlers": sum(len(v) for v in self.local_handlers.values()),
            "deduplication": {
                "enabled": self.enable_deduplication,
                "key": "tenant_id:session_id:task_id",
                "expire_seconds": self.dedup_expire_seconds,
            },
            "partition": {
                "mode": self.stream_partition_mode,
                "template": self.stream_name_template,
            },
            "pending_recovery": {
                "enabled": self.enable_pending_recovery,
                "idle_ms": self.pending_idle_ms,
                "batch": self.pending_batch,
            },
            "dlq": {
                "enabled": self.enable_dlq,
                "stream": self.dlq_stream_name,
            },
            "running": self._running,
        }


def create_message_bus(
    use_redis: bool = True,
    redis_url: str = "redis://localhost:6379",
    stream_name: str = "agent.tasks.stream",
    consumer_group: str = "task_manager_workers",
    enable_deduplication: bool = True,
    *,
    # 新增：多租户/恢复/DLQ配置（保持默认即可）
    stream_partition_mode: str = "shared",
    stream_name_template: str = "{base}:{tenant_id}",
    enable_pending_recovery: bool = True,
    pending_idle_ms: int = 60000,
    enable_dlq: bool = True,
    dlq_stream_name: str = "agent.dlq.stream",
) -> Any:
    """
    工厂函数：保持你原来调用习惯（最终版）
    """
    if not use_redis:
        raise RuntimeError("use_redis=False not supported in this final version")

    return RedisBackedEnvelopeBUS(
        redis_url=redis_url,
        stream_name=stream_name,
        consumer_group=consumer_group,
        enable_deduplication=enable_deduplication,
        stream_partition_mode=stream_partition_mode,
        stream_name_template=stream_name_template,
        enable_pending_recovery=enable_pending_recovery,
        pending_idle_ms=pending_idle_ms,
        enable_dlq=enable_dlq,
        dlq_stream_name=dlq_stream_name,
    )
