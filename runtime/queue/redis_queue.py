from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional, Tuple

from runtime.queue.task_models import TaskEnvelope


logger = logging.getLogger(__name__)


class RedisQueueError(Exception):
    """Base exception for Redis queue failures."""


class RedisQueueConfigurationError(RedisQueueError):
    """Raised when the queue client is misconfigured."""


class RedisQueueSerializationError(RedisQueueError):
    """Raised when task serialization/deserialization fails."""


class RedisQueueOperationError(RedisQueueError):
    """Raised when a Redis stream operation fails."""


class RedisStreamQueueClient:
    """
    Redis Streams queue client.

    Design goals:
    1. Support dependency injection of an already-built Redis client for tests.
    2. Keep broker payload shape stable (`{"task": "<json>"}`).
    3. Raise explicit queue-layer exceptions instead of leaking raw Redis errors.
    4. Remain compatible with current gateway/worker runtime interfaces.
    """

    def __init__(
        self,
        redis_client: Optional[Any] = None,
        redis_url: Optional[str] = None,
    ) -> None:
        self._redis = redis_client
        self._redis_url = redis_url

    async def _get_redis(self) -> Any:
        if self._redis is not None:
            return self._redis

        if not self._redis_url:
            try:
                from persistence.settings import get_settings  # local import
            except Exception as exc:  # pragma: no cover
                raise RedisQueueConfigurationError(
                    "Redis client not provided and settings loader unavailable"
                ) from exc

            settings = get_settings()
            redis_url = getattr(settings, "redis_url", None)
            if not redis_url:
                raise RedisQueueConfigurationError(
                    "Redis URL is not configured"
                )
            self._redis_url = redis_url

        try:
            import redis.asyncio as redis
        except Exception as exc:  # pragma: no cover
            raise RedisQueueConfigurationError(
                "redis.asyncio is not available"
            ) from exc

        self._redis = redis.from_url(
            self._redis_url,
            decode_responses=True,
        )
        return self._redis

    async def publish_task(self, stream_name: str, task: TaskEnvelope) -> str:
        self._validate_stream_name(stream_name)
        self._validate_task(task)

        redis_client = await self._get_redis()

        try:
            payload = json.dumps(task.model_dump(mode="json"))
        except Exception as exc:
            raise RedisQueueSerializationError(
                f"Failed to serialize task {task.task_id}"
            ) from exc

        try:
            message_id = await redis_client.xadd(
                stream_name,
                {"task": payload},
            )
        except Exception as exc:
            logger.exception(
                "Redis XADD failed",
                extra={
                    "stream_name": stream_name,
                    "task_id": task.task_id,
                },
            )
            raise RedisQueueOperationError(
                f"Failed to publish task {task.task_id} to stream {stream_name}"
            ) from exc

        if not isinstance(message_id, str) or not message_id.strip():
            raise RedisQueueOperationError(
                f"Redis returned invalid message id for task {task.task_id}"
            )

        return message_id

    async def ensure_consumer_group(
        self,
        stream_name: str,
        group_name: str,
    ) -> None:
        self._validate_stream_name(stream_name)
        self._validate_group_name(group_name)

        redis_client = await self._get_redis()

        try:
            await redis_client.xgroup_create(
                name=stream_name,
                groupname=group_name,
                id="0",
                mkstream=True,
            )
        except Exception as exc:
            message = str(exc)
            if "BUSYGROUP" in message:
                return
            logger.exception(
                "Redis XGROUP CREATE failed",
                extra={
                    "stream_name": stream_name,
                    "group_name": group_name,
                },
            )
            raise RedisQueueOperationError(
                f"Failed to ensure consumer group {group_name} for stream {stream_name}"
            ) from exc

    async def read_tasks(
        self,
        *,
        stream_name: str,
        group_name: str,
        consumer_name: str,
        count: int = 1,
        block_ms: int = 1000,
    ) -> List[Tuple[str, TaskEnvelope]]:
        self._validate_stream_name(stream_name)
        self._validate_group_name(group_name)
        self._validate_consumer_name(consumer_name)

        if count <= 0:
            raise RedisQueueConfigurationError("count must be > 0")
        if block_ms < 0:
            raise RedisQueueConfigurationError("block_ms must be >= 0")

        redis_client = await self._get_redis()

        try:
            response = await redis_client.xreadgroup(
                groupname=group_name,
                consumername=consumer_name,
                streams={stream_name: ">"},
                count=count,
                block=block_ms,
            )
        except Exception as exc:
            logger.exception(
                "Redis XREADGROUP failed",
                extra={
                    "stream_name": stream_name,
                    "group_name": group_name,
                    "consumer_name": consumer_name,
                },
            )
            raise RedisQueueOperationError(
                f"Failed to read tasks from stream {stream_name}"
            ) from exc

        if not response:
            return []

        messages: List[Tuple[str, TaskEnvelope]] = []

        try:
            for returned_stream, stream_messages in response:
                if returned_stream != stream_name:
                    logger.warning(
                        "Received message from unexpected stream",
                        extra={
                            "expected_stream": stream_name,
                            "returned_stream": returned_stream,
                        },
                    )

                for message_id, fields in stream_messages:
                    raw_task = fields.get("task")
                    if not raw_task:
                        raise RedisQueueSerializationError(
                            f"Message {message_id} missing 'task' field"
                        )

                    decoded = json.loads(raw_task)
                    task = TaskEnvelope.model_validate(decoded)
                    messages.append((message_id, task))
        except RedisQueueSerializationError:
            raise
        except Exception as exc:
            raise RedisQueueSerializationError(
                f"Failed to decode task message from stream {stream_name}"
            ) from exc

        return messages

    async def ack_task(
        self,
        *,
        stream_name: str,
        group_name: str,
        message_id: str,
    ) -> None:
        self._validate_stream_name(stream_name)
        self._validate_group_name(group_name)
        if not isinstance(message_id, str) or not message_id.strip():
            raise RedisQueueConfigurationError(
                "message_id must be a non-empty string"
            )

        redis_client = await self._get_redis()

        try:
            await redis_client.xack(
                stream_name,
                group_name,
                message_id,
            )
        except Exception as exc:
            logger.exception(
                "Redis XACK failed",
                extra={
                    "stream_name": stream_name,
                    "group_name": group_name,
                    "message_id": message_id,
                },
            )
            raise RedisQueueOperationError(
                f"Failed to ack message {message_id} on stream {stream_name}"
            ) from exc

    @staticmethod
    def _validate_task(task: TaskEnvelope) -> None:
        if not isinstance(task, TaskEnvelope):
            raise RedisQueueConfigurationError(
                f"task must be TaskEnvelope, got {type(task)!r}"
            )
        if not task.task_id or not task.task_id.strip():
            raise RedisQueueConfigurationError(
                "task.task_id must be a non-empty string"
            )

    @staticmethod
    def _validate_stream_name(stream_name: str) -> None:
        if not isinstance(stream_name, str) or not stream_name.strip():
            raise RedisQueueConfigurationError(
                "stream_name must be a non-empty string"
            )

    @staticmethod
    def _validate_group_name(group_name: str) -> None:
        if not isinstance(group_name, str) or not group_name.strip():
            raise RedisQueueConfigurationError(
                "group_name must be a non-empty string"
            )

    @staticmethod
    def _validate_consumer_name(consumer_name: str) -> None:
        if not isinstance(consumer_name, str) or not consumer_name.strip():
            raise RedisQueueConfigurationError(
                "consumer_name must be a non-empty string"
            )