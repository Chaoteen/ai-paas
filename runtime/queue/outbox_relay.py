from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from persistence.repositories.outbox_repository import OutboxRepository
from runtime.queue.redis_queue import RedisStreamQueueClient


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(slots=True)
class OutboxRelayResult:
    scanned: int
    published: int
    failed: int


class OutboxRelayError(Exception):
    """Base exception for outbox relay failures."""


class OutboxRelay:
    """
    Relay runtime_outbox_events to Redis Streams.

    Responsibilities:
    1. Load publishable outbox events from Postgres.
    2. Mark an event as publishing.
    3. Publish its payload to Redis Streams.
    4. Mark the event as published or failed.

    This relay is intentionally decoupled from gateway submit flow.
    Submit persists to DB; relay handles broker publication.
    """

    def __init__(
        self,
        *,
        session_factory: Callable[[], AsyncSession],
        queue_client: RedisStreamQueueClient,
        retry_backoff_seconds: int = 5,
    ) -> None:
        if session_factory is None:
            raise OutboxRelayError("session_factory must not be None")
        if queue_client is None:
            raise OutboxRelayError("queue_client must not be None")
        if retry_backoff_seconds < 0:
            raise OutboxRelayError("retry_backoff_seconds must be >= 0")

        self._session_factory = session_factory
        self._queue_client = queue_client
        self._retry_backoff_seconds = retry_backoff_seconds

    async def run_once(self, *, limit: int = 100) -> OutboxRelayResult:
        if limit <= 0:
            raise OutboxRelayError("limit must be > 0")

        events = await self._load_publishable_events(limit=limit)

        published = 0
        failed = 0

        for event in events:
            ok = await self._process_event(event_id=event.event_id)
            if ok:
                published += 1
            else:
                failed += 1

        return OutboxRelayResult(
            scanned=len(events),
            published=published,
            failed=failed,
        )

    async def _load_publishable_events(self, *, limit: int):
        async with self._session_factory() as session:
            repo = OutboxRepository(session)
            return await repo.list_publishable_events(limit=limit)

    async def _process_event(self, *, event_id: int) -> bool:
        event = await self._mark_publishing(event_id=event_id)

        try:
            await self._queue_client.publish_task_payload(
                stream_name=event.stream_name,
                payload=event.payload_json,
            )
        except Exception as exc:
            await self._mark_failed(
                event_id=event.event_id,
                error_text=str(exc),
            )
            return False

        await self._mark_published(event_id=event.event_id)
        return True

    async def _mark_publishing(self, *, event_id: int):
        async with self._session_factory() as session:
            repo = OutboxRepository(session)
            try:
                record = await repo.mark_publishing(event_id=event_id)
                await session.commit()
                return record
            except Exception as exc:
                await session.rollback()
                raise OutboxRelayError(
                    f"Failed to mark outbox event publishing: event_id={event_id}"
                ) from exc

    async def _mark_published(self, *, event_id: int) -> None:
        async with self._session_factory() as session:
            repo = OutboxRepository(session)
            try:
                await repo.mark_published(event_id=event_id)
                await session.commit()
            except Exception as exc:
                await session.rollback()
                raise OutboxRelayError(
                    f"Failed to mark outbox event published: event_id={event_id}"
                ) from exc

    async def _mark_failed(self, *, event_id: int, error_text: str) -> None:
        next_available_at = utcnow() + timedelta(seconds=self._retry_backoff_seconds)

        async with self._session_factory() as session:
            repo = OutboxRepository(session)
            try:
                await repo.mark_failed(
                    event_id=event_id,
                    error_text=error_text,
                    next_available_at=next_available_at,
                )
                await session.commit()
            except Exception as exc:
                await session.rollback()
                raise OutboxRelayError(
                    f"Failed to mark outbox event failed: event_id={event_id}"
                ) from exc