from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from runtime.queue.task_models import TaskEnvelope

try:
    import redis.asyncio as redis_asyncio  # type: ignore
except Exception:  # pragma: no cover
    redis_asyncio = None


DEFAULT_STREAM_PREFIX = "ai-paas:queue"
DEFAULT_CONSUMER_GROUP = "ai-paas-workers"
PAYLOAD_FIELD = "payload"


@dataclass(slots=True)
class QueueMessage:
    stream: str
    message_id: str
    task: TaskEnvelope


class RedisStreamQueueClient:
    """
    Phase 16C queue client.

    Responsibilities:
    - publish TaskEnvelope into Redis Streams
    - create consumer groups
    - read tasks via XREADGROUP
    - ack processed tasks

    Notes:
    - payload is stored as a single JSON field for schema stability
    - worker execution is not part of this class
    """

    def __init__(
        self,
        redis_url: str = "redis://127.0.0.1:6379/0",
        *,
        stream_prefix: str = DEFAULT_STREAM_PREFIX,
        consumer_group: str = DEFAULT_CONSUMER_GROUP,
        client: Any = None,
    ) -> None:
        self.redis_url = redis_url
        self.stream_prefix = stream_prefix.rstrip(":")
        self.consumer_group = consumer_group

        if client is not None:
            self._client = client
        else:
            if redis_asyncio is None:
                raise RuntimeError(
                    "redis.asyncio is not available. Install redis-py or inject a client."
                )
            self._client = redis_asyncio.from_url(
                redis_url,
                decode_responses=True,
            )

    def stream_name_for_queue(self, queue_name: str) -> str:
        return f"{self.stream_prefix}:{queue_name}"

    async def close(self) -> None:
        close = getattr(self._client, "close", None)
        if callable(close):
            result = close()
            if hasattr(result, "__await__"):
                await result

    async def publish_task(self, task: TaskEnvelope) -> str:
        stream = self.stream_name_for_queue(task.queue_name)
        payload = json.dumps(task.to_dict(), ensure_ascii=False)
        message_id = await self._client.xadd(
            stream,
            {PAYLOAD_FIELD: payload},
        )
        return str(message_id)

    async def ensure_consumer_group(
        self,
        queue_name: str,
        *,
        mkstream: bool = True,
        start_id: str = "0",
    ) -> None:
        stream = self.stream_name_for_queue(queue_name)
        try:
            await self._client.xgroup_create(
                name=stream,
                groupname=self.consumer_group,
                id=start_id,
                mkstream=mkstream,
            )
        except Exception as exc:
            message = str(exc).upper()
            if "BUSYGROUP" in message:
                return
            raise

    async def read_tasks(
        self,
        queue_name: str,
        *,
        consumer_name: str,
        count: int = 10,
        block_ms: int = 1000,
    ) -> List[QueueMessage]:
        stream = self.stream_name_for_queue(queue_name)
        records = await self._client.xreadgroup(
            groupname=self.consumer_group,
            consumername=consumer_name,
            streams={stream: ">"},
            count=count,
            block=block_ms,
        )

        return self._parse_records(records)

    async def ack_task(self, queue_name: str, message_id: str) -> int:
        stream = self.stream_name_for_queue(queue_name)
        result = await self._client.xack(stream, self.consumer_group, message_id)
        return int(result)

    async def pending_count(self, queue_name: str) -> Optional[int]:
        """
        Optional helper.
        Uses XPENDING if available on the client.
        """
        stream = self.stream_name_for_queue(queue_name)
        xpending = getattr(self._client, "xpending", None)
        if not callable(xpending):
            return None

        result = await xpending(stream, self.consumer_group)
        if isinstance(result, dict) and "pending" in result:
            return int(result["pending"])
        if isinstance(result, (list, tuple)) and result:
            return int(result[0])
        return None

    def _parse_records(self, records: Any) -> List[QueueMessage]:
        parsed: List[QueueMessage] = []

        for stream_name, items in records or []:
            stream = self._decode(stream_name)

            for message_id, fields in items:
                decoded_fields = {
                    self._decode(k): self._decode(v)
                    for k, v in (fields or {}).items()
                }

                raw_payload = decoded_fields.get(PAYLOAD_FIELD)
                if raw_payload is None:
                    continue

                task_dict = json.loads(raw_payload)
                task = TaskEnvelope.from_dict(task_dict)

                parsed.append(
                    QueueMessage(
                        stream=stream,
                        message_id=self._decode(message_id),
                        task=task,
                    )
                )

        return parsed

    @staticmethod
    def _decode(value: Any) -> Any:
        if isinstance(value, bytes):
            return value.decode("utf-8")
        return value