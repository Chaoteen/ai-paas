from __future__ import annotations

import asyncio
import os
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from bootstrap.outbox_relay_runner import build_outbox_relay
from bootstrap.runtime_worker_runner import _build_worker
from gateway.main import app
from runtime.queue.postgres_task_store import PostgresTaskStore
from runtime.queue.redis_queue import RedisStreamQueueClient
from runtime.queue.task_store import (
    get_postgres_session_factory,
    reset_task_store,
)


pytestmark = pytest.mark.asyncio


def _require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        pytest.skip(f"{name} is required for Phase 17 integration test")
    return value


def _redis_url() -> str:
    return os.getenv("REDIS_URL", "redis://127.0.0.1:6379").strip()


async def _clear_runtime_redis_streams() -> None:
    queue = RedisStreamQueueClient(redis_url=_redis_url())
    redis_client = await queue._get_redis()  # noqa: SLF001 - integration setup

    streams = [
        "agent_tasks",
        "generation_tasks",
    ]
    groups = [
        ("agent_tasks", "agent_workers"),
        ("generation_tasks", "generation_workers"),
    ]

    try:
        for stream_name, group_name in groups:
            try:
                await redis_client.xgroup_destroy(stream_name, group_name)
            except Exception:
                pass

        for stream_name in streams:
            try:
                await redis_client.delete(stream_name)
            except Exception:
                pass
    finally:
        try:
            await redis_client.aclose()
        except Exception:
            pass


async def _clear_runtime_tables() -> None:
    from persistence.db import Database
    from persistence.settings import PostgresSettings

    db = Database(PostgresSettings())
    async with db._session_factory() as session:  # noqa: SLF001 - integration setup
        await session.execute(text("DELETE FROM runtime_outbox_events"))
        await session.execute(text("DELETE FROM runtime_tasks"))
        await session.commit()
    await db.engine.dispose()


async def _poll_task(task_id: str, *, timeout_seconds: float = 20.0) -> dict:
    transport = ASGITransport(app=app)

    deadline = asyncio.get_running_loop().time() + timeout_seconds
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        while asyncio.get_running_loop().time() < deadline:
            response = await client.get(f"/api/v1/tasks/{task_id}")
            assert response.status_code == 200, response.text
            body = response.json()
            if body["status"] in {"succeeded", "failed"}:
                return body
            await asyncio.sleep(0.25)

    raise AssertionError(f"Task did not finish within {timeout_seconds} seconds: {task_id}")


async def _run_relay_once() -> None:
    relay = await build_outbox_relay()
    await relay.run_once(limit=100)

    queue_client = getattr(relay, "queue_client", None) or getattr(relay, "_queue_client", None)
    if queue_client is not None:
        redis_client = getattr(queue_client, "_redis", None)
        if redis_client is not None:
            try:
                await redis_client.aclose()
            except Exception:
                pass


async def _run_agent_worker_until_idle() -> None:
    queue = RedisStreamQueueClient(redis_url=_redis_url())
    session_factory = await get_postgres_session_factory()
    store = PostgresTaskStore(session_factory=session_factory)
    worker = _build_worker("agent", queue, store, "agent-worker-it")

    try:
        for _ in range(10):
            processed = await worker.run_once(count=10, block_ms=100)
            if processed == 0:
                break
    finally:
        redis_client = getattr(queue, "_redis", None)
        if redis_client is not None:
            try:
                await redis_client.aclose()
            except Exception:
                pass


async def _get_persisted_task(task_id: str):
    session_factory = await get_postgres_session_factory()
    store = PostgresTaskStore(session_factory=session_factory)
    return await store.get(task_id)


@pytest.fixture(autouse=True)
async def _phase17_env_guard():
    os.environ["TASK_STORE_BACKEND"] = "postgres"
    _require_env("POSTGRES_HOST")
    _require_env("POSTGRES_PORT")
    _require_env("POSTGRES_DB")
    _require_env("POSTGRES_USER")
    _require_env("POSTGRES_PASSWORD")
    os.environ.setdefault("REDIS_URL", "redis://127.0.0.1:6379")

    await reset_task_store()
    await _clear_runtime_tables()
    await _clear_runtime_redis_streams()

    yield

    await reset_task_store()


async def test_phase17_agent_submit_relay_worker_e2e():
    tenant_id = "dev"
    prompt = f"phase17 integration {uuid.uuid4()}"

    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        submit_response = await client.post(
            "/api/v1/agent/submit",
            json={
                "tenant_id": tenant_id,
                "prompt": prompt,
                "model": "qwen",
                "system_prompt": "You are a helpful assistant.",
                "temperature": 0.7,
                "max_tokens": 64,
                "metadata": {
                    "source": "phase17-integration-test",
                },
            },
        )

    assert submit_response.status_code == 202, submit_response.text
    submit_body = submit_response.json()

    assert submit_body["durable"] is True
    assert submit_body["status"] == "queued"
    assert submit_body["queue_name"] == "agent_tasks"
    assert submit_body["stream_name"] == "agent_tasks"
    assert isinstance(submit_body["outbox_event_id"], int)

    task_id = submit_body["task_id"]

    persisted = await _get_persisted_task(task_id)
    assert persisted is not None
    assert persisted.status.value == "queued"
    assert persisted.queue_name == "agent_tasks"

    await _run_relay_once()
    await _run_agent_worker_until_idle()

    task_body = await _poll_task(task_id)

    assert task_body["task_id"] == task_id
    assert task_body["status"] == "succeeded"
    assert task_body["result"] is not None
    assert task_body["result"]["status"] == "accepted"
    assert task_body["result"]["prompt"] == prompt
    assert task_body["result"]["model"] == "qwen"