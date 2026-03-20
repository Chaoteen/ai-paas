from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, List, Optional

from sqlalchemy import Select, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from persistence.models import RuntimeOutboxEventRecord


class OutboxRepositoryError(Exception):
    """Base exception for outbox repository failures."""


class OutboxEventConflictError(OutboxRepositoryError):
    """Raised when an outbox event conflicts with an existing unique constraint."""


class OutboxEventNotFoundError(OutboxRepositoryError):
    """Raised when an outbox event cannot be found."""


# Backward-compatible aliases expected by existing tests / services.
OutboxRepositoryConflictError = OutboxEventConflictError
OutboxRepositoryNotFoundError = OutboxEventNotFoundError


class OutboxRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_task_queued_event(
        self,
        *,
        task_id: str,
        tenant_id: str,
        queue_name: str,
        stream_name: str,
        payload_json: dict,
    ) -> RuntimeOutboxEventRecord:
        existing = await self._find_existing_task_queued_event(task_id=task_id)
        if existing is not None:
            raise OutboxEventConflictError(
                f"Outbox task.queued event already exists for task_id={task_id}"
            )

        now = datetime.now(timezone.utc)

        event = RuntimeOutboxEventRecord(
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
            available_at=now,
            published_at=None,
            created_at=now,
            updated_at=now,
        )

        self._session.add(event)
        try:
            await self._session.flush()
        except IntegrityError as exc:
            raise OutboxEventConflictError(
                f"Outbox task.queued event already exists for task_id={task_id}"
            ) from exc

        return event

    async def list_publishable_events(self, *, limit: int = 100) -> List[RuntimeOutboxEventRecord]:
        now = datetime.now(timezone.utc)

        stmt: Select[tuple[RuntimeOutboxEventRecord]] = (
            select(RuntimeOutboxEventRecord)
            .where(
                RuntimeOutboxEventRecord.status.in_(["pending", "failed"]),
                RuntimeOutboxEventRecord.available_at <= now,
            )
            .order_by(
                RuntimeOutboxEventRecord.available_at.asc(),
                RuntimeOutboxEventRecord.event_id.asc(),
            )
        )

        result = await self._session.execute(stmt)
        records = self._extract_records(result)
        return records[:limit]

    async def mark_publishing(self, event_id: int) -> RuntimeOutboxEventRecord:
        event = await self._get_required(event_id)
        event.status = "publishing"
        event.updated_at = datetime.now(timezone.utc)
        await self._session.flush()
        return event

    async def mark_published(self, event_id: int) -> RuntimeOutboxEventRecord:
        event = await self._get_required(event_id)
        now = datetime.now(timezone.utc)
        event.status = "published"
        event.published_at = now
        event.last_error_text = None
        event.updated_at = now
        await self._session.flush()
        return event

    async def mark_failed(
        self,
        *,
        event_id: int,
        error_text: str,
        available_at: Optional[datetime] = None,
    ) -> RuntimeOutboxEventRecord:
        event = await self._get_required(event_id)
        now = datetime.now(timezone.utc)
        event.status = "failed"
        event.publish_attempts += 1
        event.last_error_text = error_text
        event.available_at = available_at or now
        event.updated_at = now
        await self._session.flush()
        return event

    async def mark_dead_letter(
        self,
        *,
        event_id: int,
        error_text: str,
    ) -> RuntimeOutboxEventRecord:
        event = await self._get_required(event_id)
        now = datetime.now(timezone.utc)
        event.status = "dead_letter"
        event.publish_attempts += 1
        event.last_error_text = error_text
        event.updated_at = now
        await self._session.flush()
        return event

    async def _find_existing_task_queued_event(
        self,
        *,
        task_id: str,
    ) -> Optional[RuntimeOutboxEventRecord]:
        stmt: Select[tuple[RuntimeOutboxEventRecord]] = (
            select(RuntimeOutboxEventRecord)
            .where(
                RuntimeOutboxEventRecord.aggregate_type == "task",
                RuntimeOutboxEventRecord.aggregate_id == task_id,
                RuntimeOutboxEventRecord.event_type == "task.queued",
            )
        )
        result = await self._session.execute(stmt)
        records = self._extract_records(result)
        return records[0] if records else None

    async def _get_required(self, event_id: int) -> RuntimeOutboxEventRecord:
        event = await self._session.get(RuntimeOutboxEventRecord, event_id)
        if event is None:
            raise OutboxEventNotFoundError(f"Outbox event not found: event_id={event_id}")
        return event

    def _extract_records(self, result: Any) -> List[Any]:
        candidate = result

        if hasattr(candidate, "scalars"):
            candidate = candidate.scalars()

        if hasattr(candidate, "all"):
            values = candidate.all()
            return list(values)

        if isinstance(candidate, list):
            return candidate

        try:
            return list(candidate)
        except TypeError:
            return []