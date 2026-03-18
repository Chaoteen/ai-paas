from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Optional

from runtime.queue.task_models import TaskEnvelope
from runtime.queue.task_store import TaskStore

logger = logging.getLogger(__name__)


class WorkerExecutionError(Exception):
    """Raised when a worker cannot complete task execution flow."""


class WorkerBase(ABC):
    """
    Base class for queue-driven runtime workers.

    Responsibilities:
    1. Ensure the consumer group exists.
    2. Poll one or more tasks from the broker.
    3. Transition task state through RUNNING / SUCCEEDED / FAILED.
    4. Persist state changes into TaskStore.
    5. Ack broker messages after processing completes.

    This class assumes:
    - queue.read_tasks() returns list[tuple[message_id, TaskEnvelope]]
    - queue.ack_task() acks by stream/group/message_id
    - store is async and authoritative for task state
    """

    stream_name: str = ""
    group_name: str = ""

    def __init__(
        self,
        *,
        queue: Any,
        store: TaskStore,
        consumer_name: str,
    ) -> None:
        if queue is None:
            raise ValueError("queue must not be None")
        if store is None:
            raise ValueError("store must not be None")
        if not isinstance(consumer_name, str) or not consumer_name.strip():
            raise ValueError("consumer_name must be a non-empty string")
        if not self.stream_name:
            raise ValueError("stream_name must be defined on subclass")
        if not self.group_name:
            raise ValueError("group_name must be defined on subclass")

        self.queue = queue
        self.store = store
        self.consumer_name = consumer_name.strip()

    async def run_once(self, *, count: int = 1, block_ms: int = 1000) -> int:
        """
        Process a single poll cycle.

        Returns:
            number of messages received from the queue
        """
        await self.queue.ensure_consumer_group(self.stream_name, self.group_name)

        messages = await self.queue.read_tasks(
            stream_name=self.stream_name,
            group_name=self.group_name,
            consumer_name=self.consumer_name,
            count=count,
            block_ms=block_ms,
        )

        if not messages:
            return 0

        for message_id, task in messages:
            await self._process_message(message_id=message_id, task=task)

        return len(messages)

    async def _process_message(self, *, message_id: str, task: TaskEnvelope) -> None:
        if not isinstance(task, TaskEnvelope):
            raise WorkerExecutionError(
                f"Expected TaskEnvelope, got {type(task)!r}"
            )

        try:
            task.mark_running()
            await self.store.put(task)

            result = await self.execute_task(task)

            if not isinstance(result, dict):
                raise WorkerExecutionError(
                    f"execute_task must return dict, got {type(result)!r}"
                )

            task.mark_succeeded(result)
            await self.store.put(task)

        except Exception as exc:
            logger.exception(
                "Worker task execution failed",
                extra={
                    "task_id": task.task_id,
                    "stream_name": self.stream_name,
                    "group_name": self.group_name,
                    "consumer_name": self.consumer_name,
                },
            )
            task.mark_failed(
                {
                    "type": exc.__class__.__name__,
                    "message": str(exc),
                }
            )
            await self.store.put(task)

        finally:
            await self.queue.ack_task(
                stream_name=self.stream_name,
                group_name=self.group_name,
                message_id=message_id,
            )

    @abstractmethod
    async def execute_task(self, task: TaskEnvelope) -> dict:
        """
        Execute a single task and return a structured result payload.
        """