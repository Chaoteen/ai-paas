from __future__ import annotations

from typing import Any, List, Optional

from runtime.queue.redis_queue import QueueMessage, RedisStreamQueueClient
from runtime.queue.task_models import TaskEnvelope
from runtime.queue.task_store import InMemoryTaskStore


class WorkerBase:
    """
    Phase 16D base worker loop.

    Responsibilities:
    - ensure Redis consumer group exists
    - read queued tasks from a specific queue
    - mark task state transitions
    - delegate actual execution to subclass
    - update task store
    - ack queue message when processing completes

    Subclasses must implement:
    - process_task(task: TaskEnvelope) -> dict
    """

    def __init__(
        self,
        *,
        queue_client: RedisStreamQueueClient,
        task_store: InMemoryTaskStore,
        queue_name: str,
        consumer_name: str,
    ) -> None:
        self.queue_client = queue_client
        self.task_store = task_store
        self.queue_name = queue_name
        self.consumer_name = consumer_name

    async def ensure_queue(self) -> None:
        await self.queue_client.ensure_consumer_group(self.queue_name)

    async def poll_once(self, *, count: int = 10, block_ms: int = 1000) -> int:
        messages = await self.queue_client.read_tasks(
            self.queue_name,
            consumer_name=self.consumer_name,
            count=count,
            block_ms=block_ms,
        )

        processed = 0
        for message in messages:
            await self._handle_message(message)
            processed += 1
        return processed

    async def _handle_message(self, message: QueueMessage) -> None:
        task = message.task

        # persist / refresh the queued task into the store
        self.task_store.put(task)

        task.mark_running()
        self.task_store.update(task)

        try:
            result = await self.process_task(task)
            task.mark_succeeded(result)
            self.task_store.update(task)
        except Exception as exc:
            task.increment_retry()
            task.mark_failed(
                {
                    "type": exc.__class__.__name__,
                    "message": str(exc),
                }
            )
            self.task_store.update(task)
        finally:
            await self.queue_client.ack_task(self.queue_name, message.message_id)

    async def process_task(self, task: TaskEnvelope) -> Optional[dict]:
        raise NotImplementedError