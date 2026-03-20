from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import inspect
import os
from typing import Any, Callable, Optional

from persistence.repositories.outbox_repository import OutboxRepository
from runtime.queue.redis_queue import RedisStreamQueueClient


@dataclass
class OutboxRelayResult:
    scanned: int
    published: int
    failed: int
    dead_lettered: int


class OutboxRelay:
    def __init__(
        self,
        *,
        session_factory: Callable[..., Any],
        queue_client: RedisStreamQueueClient,
        retry_backoff_seconds: int = 5,
        max_publish_attempts: Optional[int] = None,
    ) -> None:
        self._session_factory = session_factory
        self._queue_client = queue_client
        self.retry_backoff_seconds = retry_backoff_seconds
        self.max_publish_attempts = (
            max_publish_attempts
            if max_publish_attempts is not None
            else int(os.getenv("OUTBOX_MAX_PUBLISH_ATTEMPTS", "10"))
        )

    @property
    def queue_client(self) -> RedisStreamQueueClient:
        return self._queue_client

    async def run_once(self, *, limit: int = 100) -> OutboxRelayResult:
        events = await self._load_publishable_events(limit=limit)

        published = 0
        failed = 0
        dead_lettered = 0

        for event in events:
            publish_attempts = int(getattr(event, "publish_attempts", 0) or 0)

            try:
                await self._publish_event(event)
                published += 1
            except Exception as exc:
                became_dead_letter = await self._mark_failed_or_dead_letter(
                    event_id=event.event_id,
                    error_text=str(exc),
                    publish_attempts=publish_attempts,
                )
                if became_dead_letter:
                    dead_lettered += 1
                else:
                    failed += 1

        return OutboxRelayResult(
            scanned=len(events),
            published=published,
            failed=failed,
            dead_lettered=dead_lettered,
        )

    async def _load_publishable_events(self, *, limit: int):
        async with self._session_factory() as session:
            repo = OutboxRepository(session)
            return await repo.list_publishable_events(limit=limit)

    async def _publish_event(self, event) -> None:
        async with self._session_factory() as session:
            repo = OutboxRepository(session)
            await self._call_repo_method(repo, "mark_publishing", event_id=event.event_id)
            await session.commit()

        await self._call_queue_publish(
            stream_name=event.stream_name,
            payload=event.payload_json,
        )

        async with self._session_factory() as session:
            repo = OutboxRepository(session)
            await self._call_repo_method(repo, "mark_published", event_id=event.event_id)
            await session.commit()

    async def _mark_failed_or_dead_letter(
        self,
        *,
        event_id: int,
        error_text: str,
        publish_attempts: int,
    ) -> bool:
        next_attempt = publish_attempts + 1

        async with self._session_factory() as session:
            repo = OutboxRepository(session)

            if self._is_dead_letter_threshold(next_attempt):
                await self._call_repo_method(
                    repo,
                    "mark_dead_letter",
                    event_id=event_id,
                    error_text=error_text,
                )
                await session.commit()
                return True

            available_at = datetime.now(timezone.utc) + timedelta(
                seconds=self.retry_backoff_seconds
            )
            await self._call_repo_method(
                repo,
                "mark_failed",
                event_id=event_id,
                error_text=error_text,
                available_at=available_at,
            )
            await session.commit()
            return False

    def _is_dead_letter_threshold(self, attempts: int) -> bool:
        return attempts >= self.max_publish_attempts

    async def _call_queue_publish(self, *, stream_name: str, payload: dict) -> Any:
        method = getattr(self._queue_client, "publish_task_payload", None)
        if method is None:
            raise AttributeError("queue_client has no publish_task_payload method")

        try:
            return await method(stream_name=stream_name, payload=payload)
        except TypeError:
            try:
                return await method(stream_name, payload)
            except TypeError:
                return await method(payload)

    async def _call_repo_method(self, repo: Any, method_name: str, **kwargs) -> Any:
        method = getattr(repo, method_name)
        try:
            return await method(**kwargs)
        except TypeError:
            pass

        sig = inspect.signature(method)
        accepted = {
            name: value
            for name, value in kwargs.items()
            if name in sig.parameters
        }

        if accepted:
            try:
                return await method(**accepted)
            except TypeError:
                pass

        if len(sig.parameters) == 0:
            return await method()

        positional_order = [
            kwargs["event_id"]
            for name in sig.parameters
            if name == "event_id" and "event_id" in kwargs
        ]
        if positional_order:
            try:
                return await method(*positional_order)
            except TypeError:
                pass

        if "error_text" in kwargs:
            try:
                return await method(kwargs["error_text"])
            except TypeError:
                pass

        raise