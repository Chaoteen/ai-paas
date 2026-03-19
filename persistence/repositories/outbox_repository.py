from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from persistence.models import RuntimeOutboxEventRecord


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class OutboxRepositoryError(Exception):
    """Base exception for outbox repository failures."""


class OutboxRepositoryConflictError(OutboxRepositoryError):
    """Raised when an outbox event already exists and uniqueness is violated."""


class OutboxRepositoryNotFoundError(OutboxRepositoryError):
    """Raised when an outbox event cannot be found."""


class OutboxRepository:
    """
    Repository for transactional outbox records.

    Responsibilities:
    - create durable outbox rows inside the same DB transaction as runtime_tasks
    - load pending publishable events for relay workers
    - update publish state / attempts / errors
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_task_queued_event(
        self,
        *,
        tenant_id: str,
        task_id: str,
        queue_name: str,
        stream_name: str,
        payload_json: dict[str, Any],
    ) -> RuntimeOutboxEventRecord:
        existing = await self.get_by_unique_key(
            aggregate_type="task",
            aggregate_id=task_id,
            event_type="task.queued",
        )
        if existing is not None:
            raise OutboxRepositoryConflictError(
                f"Outbox event already exists for task.queued: task_id={task_id}"
            )

        record = RuntimeOutboxEventRecord(
            aggregate_type="task",
            aggregate_id=task_id,
            tenant_id=tenant_id,
            event_type="task.queued",
            queue_name=queue_name,
            stream_name=stream_name,
            payload_json=payload_json,
            status="pending",
            publish_attempts=0,
            last_error_text=None,
            available_at=utcnow(),
            published_at=None,
            created_at=utcnow(),
            updated_at=utcnow(),
        )
        self._session.add(record)
        await self._session.flush()
        return record

    async def get_by_id(self, event_id: int) -> Optional[RuntimeOutboxEventRecord]:
        return await self._session.get(RuntimeOutboxEventRecord, event_id)

    async def get_by_unique_key(
        self,
        *,
        aggregate_type: str,
        aggregate_id: str,
        event_type: str,
    ) -> Optional[RuntimeOutboxEventRecord]:
        stmt = select(RuntimeOutboxEventRecord).where(
            RuntimeOutboxEventRecord.aggregate_type == aggregate_type,
            RuntimeOutboxEventRecord.aggregate_id == aggregate_id,
            RuntimeOutboxEventRecord.event_type == event_type,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_publishable_events(
        self,
        *,
        now: Optional[datetime] = None,
        limit: int = 100,
    ) -> list[RuntimeOutboxEventRecord]:
        effective_now = now or utcnow()

        stmt = (
            select(RuntimeOutboxEventRecord)
            .where(
                RuntimeOutboxEventRecord.status.in_(["pending", "failed"]),
                RuntimeOutboxEventRecord.available_at <= effective_now,
            )
            .order_by(
                RuntimeOutboxEventRecord.available_at.asc(),
                RuntimeOutboxEventRecord.event_id.asc(),
            )
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def mark_publishing(
        self,
        *,
        event_id: int,
    ) -> RuntimeOutboxEventRecord:
        record = await self._session.get(RuntimeOutboxEventRecord, event_id)
        if record is None:
            raise OutboxRepositoryNotFoundError(
                f"Outbox event not found: event_id={event_id}"
            )

        record.status = "publishing"
        record.updated_at = utcnow()
        await self._session.flush()
        return record

    async def mark_published(
        self,
        *,
        event_id: int,
        published_at: Optional[datetime] = None,
    ) -> RuntimeOutboxEventRecord:
        record = await self._session.get(RuntimeOutboxEventRecord, event_id)
        if record is None:
            raise OutboxRepositoryNotFoundError(
                f"Outbox event not found: event_id={event_id}"
            )

        record.status = "published"
        record.published_at = published_at or utcnow()
        record.last_error_text = None
        record.updated_at = utcnow()
        await self._session.flush()
        return record

    async def mark_failed(
        self,
        *,
        event_id: int,
        error_text: str,
        next_available_at: Optional[datetime] = None,
    ) -> RuntimeOutboxEventRecord:
        record = await self._session.get(RuntimeOutboxEventRecord, event_id)
        if record is None:
            raise OutboxRepositoryNotFoundError(
                f"Outbox event not found: event_id={event_id}"
            )

        record.status = "failed"
        record.publish_attempts += 1
        record.last_error_text = error_text
        record.available_at = next_available_at or utcnow()
        record.updated_at = utcnow()
        await self._session.flush()
        return record