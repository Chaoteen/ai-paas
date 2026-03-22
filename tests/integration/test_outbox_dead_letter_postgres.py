from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import text

from persistence.db import Database
from persistence.settings import PostgresSettings
from persistence.repositories.outbox_repository import OutboxRepository
from runtime.queue.outbox_relay import OutboxRelay
from runtime.queue.task_store import get_postgres_session_factory


pytestmark = pytest.mark.asyncio


def _require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        pytest.skip(f"{name} is required for Postgres integration test")
    return value


class FailingQueue:
    async def publish_task_payload(self, *, stream_name: str, payload: dict):
        raise RuntimeError(
            f"forced publish failure for stream={stream_name}, task_id={payload.get('task_id')}"
        )


async def _clear_runtime_tables() -> None:
    db = Database(PostgresSettings())
    async with db._session_factory() as session:  # noqa: SLF001 - integration setup
        await session.execute(text("DELETE FROM runtime_outbox_events"))
        await session.execute(text("DELETE FROM runtime_tasks"))
        await session.commit()
    await db.engine.dispose()


@pytest.fixture(autouse=True)
async def _postgres_env_guard():
    _require_env("POSTGRES_HOST")
    _require_env("POSTGRES_PORT")
    _require_env("POSTGRES_DB")
    _require_env("POSTGRES_USER")
    _require_env("POSTGRES_PASSWORD")

    await _clear_runtime_tables()
    yield
    await _clear_runtime_tables()


async def _load_outbox_row(event_id: int) -> dict:
    db = Database(PostgresSettings())
    async with db._session_factory() as session:  # noqa: SLF001 - integration readback
        result = await session.execute(
            text(
                """
                SELECT
                    event_id,
                    aggregate_id,
                    status,
                    publish_attempts,
                    last_error_text
                FROM runtime_outbox_events
                WHERE event_id = :event_id
                """
            ),
            {"event_id": event_id},
        )
        row = result.mappings().one()
    await db.engine.dispose()
    return dict(row)


async def _create_real_outbox_event() -> int:
    session_factory = await get_postgres_session_factory()
    task_id = f"dlq-task-{uuid.uuid4()}"

    async with session_factory() as session:
        repo = OutboxRepository(session)
        event = await repo.create_task_queued_event(
            tenant_id="dev",
            task_id=task_id,
            queue_name="agent_tasks",
            stream_name="agent_tasks",
            payload_json={
                "task_id": task_id,
                "tenant_id": "dev",
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        await session.commit()
        return int(event.event_id)


async def test_outbox_event_moves_to_dead_letter_after_reaching_retry_threshold():
    event_id = await _create_real_outbox_event()
    session_factory = await get_postgres_session_factory()

    relay = OutboxRelay(
        session_factory=session_factory,
        queue_client=FailingQueue(),
        retry_backoff_seconds=0,
        max_publish_attempts=2,
    )

    first = await relay.run_once(limit=100)
    assert first.scanned == 1
    assert first.published == 0
    assert first.failed == 1
    assert first.dead_lettered == 0

    row_after_first = await _load_outbox_row(event_id)
    assert row_after_first["status"] == "failed"
    assert row_after_first["publish_attempts"] == 1
    assert "forced publish failure" in row_after_first["last_error_text"]

    second = await relay.run_once(limit=100)
    assert second.scanned == 1
    assert second.published == 0
    assert second.failed == 0
    assert second.dead_lettered == 1

    row_after_second = await _load_outbox_row(event_id)
    assert row_after_second["status"] == "dead_letter"
    assert row_after_second["publish_attempts"] == 2
    assert "forced publish failure" in row_after_second["last_error_text"]