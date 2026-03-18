from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Optional, Protocol, runtime_checkable

from runtime.queue.task_models import TaskEnvelope, TaskStatus
from runtime.queue.task_store import TaskStore


logger = logging.getLogger(__name__)


class TaskDispatchError(Exception):
    """Raised when a task cannot be dispatched to the runtime queue."""


class TaskDispatchValidationError(TaskDispatchError):
    """Raised when the task or queue routing information is invalid."""


class TaskDispatchPersistenceError(TaskDispatchError):
    """Raised when task state persistence fails before or after publish."""


@runtime_checkable
class DispatchQueue(Protocol):
    async def publish_task(self, stream_name: str, task: TaskEnvelope) -> str:
        """
        Publish a task into the target stream and return the broker message id.
        """


@dataclass(slots=True)
class DispatchResult:
    task_id: str
    queue_name: str
    stream_name: str
    message_id: str
    status: str


class TaskDispatcher:
    """
    Production-oriented task dispatcher.

    Responsibilities:
    1. Validate routing input.
    2. Transition task state to QUEUED.
    3. Persist queued state before broker publish.
    4. Publish task to the queue broker.
    5. Persist failure state if publish fails.

    Design notes:
    - This class is intentionally strict about task lifecycle transitions.
    - It does not silently coerce invalid queue names or task states.
    - It assumes the TaskStore is the source of truth for task state.
    - It does not implement transactional outbox yet; that is the next step.
    """

    def __init__(
        self,
        *,
        store: TaskStore,
        queue: DispatchQueue,
    ) -> None:
        if store is None:
            raise TaskDispatchValidationError("store must not be None")
        if queue is None:
            raise TaskDispatchValidationError("queue must not be None")
        if not isinstance(queue, DispatchQueue):
            raise TaskDispatchValidationError(
                "queue must implement publish_task(stream_name, task)"
            )

        self._store = store
        self._queue = queue

    async def dispatch(self, *, stream_name: str, task: TaskEnvelope) -> str:
        """
        Persist the task as queued, publish it, and return the broker message id.

        Failure handling:
        - If initial persistence fails, raise TaskDispatchPersistenceError.
        - If broker publish fails, mark the task FAILED and persist that state.
        - If failure persistence also fails, raise a composed TaskDispatchError.
        """
        self._validate_stream_name(stream_name)
        self._validate_task(task)

        # Enforce routing consistency early.
        if not task.queue_name or not task.queue_name.strip():
            raise TaskDispatchValidationError(
                f"Task {task.task_id} has empty queue_name"
            )

        # Phase 16F policy: dispatcher owns the transition to queued state.
        if task.status != TaskStatus.QUEUED:
            task.mark_queued()

        try:
            await self._store.put(task)
        except Exception as exc:  # pragma: no cover - backend-specific failure path
            logger.exception(
                "Failed to persist queued task before publish",
                extra={
                    "task_id": task.task_id,
                    "queue_name": task.queue_name,
                    "stream_name": stream_name,
                },
            )
            raise TaskDispatchPersistenceError(
                f"Failed to persist queued task before publish: task_id={task.task_id}"
            ) from exc

        try:
            message_id = await self._queue.publish_task(stream_name, task)
        except Exception as exc:
            logger.exception(
                "Failed to publish task to queue",
                extra={
                    "task_id": task.task_id,
                    "queue_name": task.queue_name,
                    "stream_name": stream_name,
                },
            )
            await self._mark_failed_after_publish_error(task=task, cause=exc)
            raise TaskDispatchError(
                f"Failed to dispatch task {task.task_id} to stream {stream_name}"
            ) from exc

        if not isinstance(message_id, str) or not message_id.strip():
            publish_error = TaskDispatchError(
                f"Queue returned invalid message_id for task {task.task_id}"
            )
            await self._mark_failed_after_publish_error(task=task, cause=publish_error)
            raise publish_error

        return message_id

    async def dispatch_and_report(
        self,
        *,
        stream_name: str,
        task: TaskEnvelope,
    ) -> DispatchResult:
        """
        Same as dispatch(), but returns a structured result.
        """
        message_id = await self.dispatch(stream_name=stream_name, task=task)
        return DispatchResult(
            task_id=task.task_id,
            queue_name=task.queue_name,
            stream_name=stream_name,
            message_id=message_id,
            status=task.status.value,
        )

    async def _mark_failed_after_publish_error(
        self,
        *,
        task: TaskEnvelope,
        cause: BaseException,
    ) -> None:
        task.mark_failed(
            {
                "type": cause.__class__.__name__,
                "message": str(cause),
            }
        )

        try:
            await self._store.put(task)
        except Exception as persist_exc:  # pragma: no cover - backend-specific path
            logger.exception(
                "Failed to persist failed task state after publish error",
                extra={
                    "task_id": task.task_id,
                    "queue_name": task.queue_name,
                },
            )
            raise TaskDispatchPersistenceError(
                "Task publish failed and failed state could not be persisted: "
                f"task_id={task.task_id}"
            ) from persist_exc

    @staticmethod
    def _validate_stream_name(stream_name: str) -> None:
        if not isinstance(stream_name, str) or not stream_name.strip():
            raise TaskDispatchValidationError(
                "stream_name must be a non-empty string"
            )

    @staticmethod
    def _validate_task(task: Optional[TaskEnvelope]) -> None:
        if task is None:
            raise TaskDispatchValidationError("task must not be None")
        if not isinstance(task, TaskEnvelope):
            raise TaskDispatchValidationError(
                f"task must be TaskEnvelope, got {type(task)!r}"
            )
        if not task.task_id or not task.task_id.strip():
            raise TaskDispatchValidationError("task.task_id must not be empty")