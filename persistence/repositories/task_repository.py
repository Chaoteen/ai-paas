from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from persistence.models import RuntimeTaskRecord
from runtime.queue.task_models import TaskEnvelope, TaskStatus, TaskType


class TaskRepositoryError(Exception):
    """Base exception for task repository failures."""


class TaskRepositoryConflictError(TaskRepositoryError):
    """Raised when attempting to create a duplicate task."""


class TaskRepositoryNotFoundError(TaskRepositoryError):
    """Raised when task record is not found."""


class TaskRepository:
    """
    Repository for durable runtime task persistence.

    Responsibilities:
    - map TaskEnvelope <-> RuntimeTaskRecord
    - create / update / get task rows
    - provide a single persistence boundary for Postgres-backed TaskStore
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, task: TaskEnvelope) -> RuntimeTaskRecord:
        existing = await self._session.get(RuntimeTaskRecord, task.task_id)
        if existing is not None:
            raise TaskRepositoryConflictError(
                f"Task already exists: task_id={task.task_id}"
            )

        record = self._to_record(task)
        self._session.add(record)
        await self._session.flush()
        return record

    async def upsert(self, task: TaskEnvelope) -> RuntimeTaskRecord:
        record = await self._session.get(RuntimeTaskRecord, task.task_id)
        if record is None:
            record = self._to_record(task)
            self._session.add(record)
        else:
            self._apply_task_to_record(task, record)

        await self._session.flush()
        return record

    async def update(self, task: TaskEnvelope) -> RuntimeTaskRecord:
        record = await self._session.get(RuntimeTaskRecord, task.task_id)
        if record is None:
            raise TaskRepositoryNotFoundError(
                f"Task not found: task_id={task.task_id}"
            )

        self._apply_task_to_record(task, record)
        await self._session.flush()
        return record

    async def get(self, task_id: str) -> Optional[TaskEnvelope]:
        record = await self._session.get(RuntimeTaskRecord, task_id)
        if record is None:
            return None
        return self._to_task(record)

    async def get_record(self, task_id: str) -> Optional[RuntimeTaskRecord]:
        return await self._session.get(RuntimeTaskRecord, task_id)

    async def get_by_tenant_and_idempotency_key(
        self,
        *,
        tenant_id: str,
        idempotency_key: str,
    ) -> Optional[TaskEnvelope]:
        stmt = select(RuntimeTaskRecord).where(
            RuntimeTaskRecord.tenant_id == tenant_id,
            RuntimeTaskRecord.idempotency_key == idempotency_key,
        )
        result = await self._session.execute(stmt)
        record = result.scalar_one_or_none()
        if record is None:
            return None
        return self._to_task(record)

    @staticmethod
    def _to_record(task: TaskEnvelope) -> RuntimeTaskRecord:
        return RuntimeTaskRecord(
            task_id=task.task_id,
            tenant_id=task.tenant_id,
            task_type=task.task_type.value,
            queue_name=task.queue_name,
            status=task.status.value,
            payload_json=task.payload,
            result_json=task.result,
            error_text=task.error,
            retry_count=task.retry_count,
            correlation_id=task.correlation_id,
            idempotency_key=task.idempotency_key,
            created_at=task.created_at,
            queued_at=task.queued_at,
            started_at=task.started_at,
            finished_at=task.finished_at,
            updated_at=datetime.utcnow(),
        )

    @staticmethod
    def _apply_task_to_record(
        task: TaskEnvelope,
        record: RuntimeTaskRecord,
    ) -> None:
        record.tenant_id = task.tenant_id
        record.task_type = task.task_type.value
        record.queue_name = task.queue_name
        record.status = task.status.value
        record.payload_json = task.payload
        record.result_json = task.result
        record.error_text = task.error
        record.retry_count = task.retry_count
        record.correlation_id = task.correlation_id
        record.idempotency_key = task.idempotency_key
        record.created_at = task.created_at
        record.queued_at = task.queued_at
        record.started_at = task.started_at
        record.finished_at = task.finished_at
        record.updated_at = datetime.utcnow()

    @staticmethod
    def _to_task(record: RuntimeTaskRecord) -> TaskEnvelope:
        return TaskEnvelope(
            task_id=record.task_id,
            tenant_id=record.tenant_id,
            task_type=TaskType(record.task_type),
            queue_name=record.queue_name,
            status=TaskStatus(record.status),
            payload=record.payload_json,
            result=record.result_json,
            error=record.error_text,
            created_at=record.created_at,
            queued_at=record.queued_at,
            started_at=record.started_at,
            finished_at=record.finished_at,
            retry_count=record.retry_count,
            correlation_id=record.correlation_id,
            idempotency_key=record.idempotency_key,
        )