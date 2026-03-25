from __future__ import annotations

import os
from uuid import uuid4

import asyncpg
import pytest

from persistence.repositories.outbox_repository import OutboxRepository
from persistence.repositories.task_repository import TaskRepository
from runtime.queue.outbox_relay import OutboxRelay
from runtime.queue.task_store import get_postgres_session_factory
from runtime.queue.task_models import TaskEnvelope, TaskStatus, TaskType


pytestmark = pytest.mark.asyncio


def _require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        pytest.skip(f"{name} is required for postgres integration test")
    return value


def _postgres_dsn() -> dict[str, object]:
    return {
        "host": _require_env("POSTGRES_HOST"),
        "port": int(os.getenv("POSTGRES_PORT", "5432").strip()),
        "database": _require_env("POSTGRES_DB"),
        "user": _require_env("POSTGRES_USER"),
        "password": _require_env("POSTGRES_PASSWORD"),
    }


class AlwaysFailQueueClient:
    async def publish_task_payload(self, *, stream_name: str, payload: dict):
        raise RuntimeError("simulated redis publish failure")


@pytest.fixture(autouse=True)
async def _clean_runtime_tables():
    conn = await asyncpg.connect(**_postgres_dsn())
    try:
        await conn.execute(
            "TRUNCATE TABLE runtime_outbox_events, runtime_tasks RESTART IDENTITY"
        )
        yield
        await conn.execute(
            "TRUNCATE TABLE runtime_outbox_events, runtime_tasks RESTART IDENTITY"
        )
    finally:
        await conn.close()


async def _insert_task_and_outbox_event() -> tuple[str, int]:
    session_factory = await get_postgres_session_factory()
    task_id = f"task-{uuid4()}"

    task = TaskEnvelope(
        task_id=task_id,
        tenant_id="test-tenant",
        task_type=TaskType.AGENT,
        queue_name="agent_tasks",
        status=TaskStatus.QUEUED,
        payload={"message": "hello"},
        result=None,
        error=None,
        retry_count=0,
        correlation_id=None,
        idempotency_key=None,
    )

    async with session_factory() as session:
        task_repo = TaskRepository(session)
        outbox_repo = OutboxRepository(session)

        await task_repo.create(task)
        event = await outbox_repo.create_task_queued_event(
            task_id=task_id,
            tenant_id=task.tenant_id,
            queue_name=task.queue_name,
            stream_name="agent_tasks",
            payload_json={"task_id": task_id},
        )

        await session.commit()
        return task_id, event.event_id


async def _fetch_outbox_row(event_id: int) -> asyncpg.Record:
    conn = await asyncpg.connect(**_postgres_dsn())
    try:
        row = await conn.fetchrow(
            """
            SELECT event_id, status, publish_attempts, last_error_text
            FROM runtime_outbox_events
            WHERE event_id = $1
            """,
            event_id,
        )
        assert row is not None
        return row
    finally:
        await conn.close()


async def test_outbox_event_moves_to_dead_letter_after_reaching_retry_threshold():
    task_id, event_id = await _insert_task_and_outbox_event()

    relay = OutboxRelay(
        session_factory=await get_postgres_session_factory(),
        queue_client=AlwaysFailQueueClient(),
        retry_backoff_seconds=0,
        max_publish_attempts=2,
    )

    first = await relay.run_once(limit=100)

    assert first.scanned == 1
    assert first.published == 0
    assert first.failed == 1
    assert first.dead_lettered == 0

    first_row = await _fetch_outbox_row(event_id)
    assert first_row["status"] == "failed"
    assert first_row["publish_attempts"] == 1
    assert "simulated redis publish failure" in (first_row["last_error_text"] or "")

    second = await relay.run_once(limit=100)

    assert second.scanned == 1
    assert second.published == 0
    assert second.failed == 0
    assert second.dead_lettered == 1

    second_row = await _fetch_outbox_row(event_id)
    assert second_row["status"] == "dead_letter"
    assert second_row["publish_attempts"] == 2
    assert "simulated redis publish failure" in (second_row["last_error_text"] or "")

    assert task_id.startswith("task-")