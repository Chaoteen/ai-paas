from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from persistence.repositories.outbox_repository import (
    OutboxRepository,
    OutboxRepositoryConflictError,
)
from persistence.repositories.task_repository import (
    TaskRepository,
    TaskRepositoryConflictError,
)
from runtime.queue.task_models import TaskEnvelope
from runtime.queue.task_store import TaskStoreConflictError


@dataclass(slots=True)
class TaskSubmissionResult:
    task_id: str
    queue_name: str
    stream_name: str
    outbox_event_id: int
    status: str


class TaskSubmissionServiceError(Exception):
    """Base exception for transactional task submission failures."""


class TaskSubmissionConflictError(TaskSubmissionServiceError):
    """Raised when a task or idempotent submission already exists."""


class TaskSubmissionService:
    """
    Transactional task submission service.

    Responsibilities:
    1. Persist runtime_tasks and runtime_outbox_events in the same DB transaction.
    2. Enforce a single durable source of truth before any relay publishes to Redis.
    3. Provide an idempotency-aware foundation for future API integration.

    This service intentionally does NOT publish directly to Redis.
    Publish responsibility belongs to the future outbox relay worker.
    """

    def __init__(
        self,
        session_factory: Callable[[], AsyncSession],
    ) -> None:
        if session_factory is None:
            raise TaskSubmissionServiceError("session_factory must not be None")
        self._session_factory = session_factory

    async def submit_task(
        self,
        *,
        task: TaskEnvelope,
        stream_name: Optional[str] = None,
    ) -> TaskSubmissionResult:
        self._validate_task(task)

        effective_stream_name = (stream_name or task.queue_name).strip()
        if not effective_stream_name:
            raise TaskSubmissionServiceError("stream_name must not be empty")

        async with self._session_factory() as session:
            task_repo = TaskRepository(session)
            outbox_repo = OutboxRepository(session)

            try:
                existing = await self._find_existing_by_idempotency(
                    task_repo=task_repo,
                    tenant_id=task.tenant_id,
                    idempotency_key=task.idempotency_key,
                )
                if existing is not None:
                    raise TaskSubmissionConflictError(
                        "Task submission already exists for tenant/idempotency_key: "
                        f"tenant_id={task.tenant_id}, idempotency_key={task.idempotency_key}"
                    )

                if task.status.value != "queued":
                    task.mark_queued()

                await task_repo.create(task)

                outbox_record = await outbox_repo.create_task_queued_event(
                    tenant_id=task.tenant_id,
                    task_id=task.task_id,
                    queue_name=task.queue_name,
                    stream_name=effective_stream_name,
                    payload_json=task.as_queue_message(),
                )

                await session.commit()

                return TaskSubmissionResult(
                    task_id=task.task_id,
                    queue_name=task.queue_name,
                    stream_name=effective_stream_name,
                    outbox_event_id=outbox_record.event_id,
                    status=task.status.value,
                )

            except (
                TaskRepositoryConflictError,
                OutboxRepositoryConflictError,
                TaskSubmissionConflictError,
            ) as exc:
                await session.rollback()
                raise TaskSubmissionConflictError(str(exc)) from exc
            except Exception as exc:
                await session.rollback()
                raise TaskSubmissionServiceError(
                    f"Failed to submit task transactionally: task_id={task.task_id}"
                ) from exc

    async def _find_existing_by_idempotency(
        self,
        *,
        task_repo: TaskRepository,
        tenant_id: str,
        idempotency_key: Optional[str],
    ) -> Optional[TaskEnvelope]:
        if idempotency_key is None or not idempotency_key.strip():
            return None

        return await task_repo.get_by_tenant_and_idempotency_key(
            tenant_id=tenant_id,
            idempotency_key=idempotency_key,
        )

    @staticmethod
    def _validate_task(task: TaskEnvelope) -> None:
        if not isinstance(task, TaskEnvelope):
            raise TaskSubmissionServiceError(
                f"task must be TaskEnvelope, got {type(task)!r}"
            )
        if not task.task_id or not task.task_id.strip():
            raise TaskSubmissionServiceError("task.task_id must not be empty")
        if not task.tenant_id or not task.tenant_id.strip():
            raise TaskSubmissionServiceError("task.tenant_id must not be empty")
        if not task.queue_name or not task.queue_name.strip():
            raise TaskSubmissionServiceError("task.queue_name must not be empty")