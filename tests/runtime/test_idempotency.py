import pytest

from runtime.idempotency import (
    InMemoryIdempotencyStore,
    build_event_stage_key,
    build_event_type_key,
)


@pytest.mark.asyncio
async def test_idempotency_acquire_first_time_returns_true() -> None:
    store = InMemoryIdempotencyStore()

    ok = await store.acquire(
        key=build_event_stage_key(task_id="task-001", stage="executing"),
        owner="agent-worker-1",
    )

    assert ok is True


@pytest.mark.asyncio
async def test_idempotency_second_acquire_returns_false() -> None:
    store = InMemoryIdempotencyStore()
    key = build_event_type_key(task_id="task-001", event_type="router.success")

    first = await store.acquire(key=key, owner="router-worker-1")
    second = await store.acquire(key=key, owner="router-worker-2")

    assert first is True
    assert second is False

    record = await store.get(key)
    assert record is not None
    assert record.owner == "router-worker-1"
    assert record.hit_count == 2


@pytest.mark.asyncio
async def test_idempotency_release_allows_reacquire() -> None:
    store = InMemoryIdempotencyStore()
    key = build_event_stage_key(task_id="task-002", stage="executing")

    first = await store.acquire(key=key, owner="agent-worker-1")
    await store.release(key)
    second = await store.acquire(key=key, owner="agent-worker-2")

    assert first is True
    assert second is True

    record = await store.get(key)
    assert record is not None
    assert record.owner == "agent-worker-2"


def test_idempotency_key_builders() -> None:
    assert build_event_stage_key(task_id="task-100", stage="executing") == "task:task-100:stage:executing"
    assert build_event_type_key(task_id="task-100", event_type="router.success") == "task:task-100:event:router.success"