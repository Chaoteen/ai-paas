import pytest

import runtime.queue.task_store as task_store_mod
from runtime.queue.task_store import (
    InMemoryTaskStore,
    TaskStoreError,
    get_task_store,
    get_task_store_backend_name,
    reset_task_store,
)


def test_get_task_store_backend_name_defaults_to_memory(monkeypatch):
    monkeypatch.delenv("TASK_STORE_BACKEND", raising=False)
    assert get_task_store_backend_name() == "memory"


def test_get_task_store_backend_name_accepts_postgres(monkeypatch):
    monkeypatch.setenv("TASK_STORE_BACKEND", "postgres")
    assert get_task_store_backend_name() == "postgres"


@pytest.mark.asyncio
async def test_get_task_store_returns_memory_by_default(monkeypatch):
    monkeypatch.delenv("TASK_STORE_BACKEND", raising=False)
    await reset_task_store()
    store = await get_task_store()
    assert isinstance(store, InMemoryTaskStore)


@pytest.mark.asyncio
async def test_get_task_store_uses_custom_builder(monkeypatch):
    class DummyStore:
        pass

    dummy_store = DummyStore()

    async def fake_build():
        return dummy_store

    monkeypatch.setenv("TASK_STORE_BACKEND", "postgres")
    await reset_task_store()
    monkeypatch.setattr(task_store_mod, "_build_task_store", fake_build)

    store = await get_task_store()
    assert store is dummy_store


def test_build_backend_name_is_lowercased(monkeypatch):
    monkeypatch.setenv("TASK_STORE_BACKEND", "PoStGrEs")
    assert get_task_store_backend_name() == "postgres"


@pytest.mark.asyncio
async def test_get_task_store_invalid_backend_raises(monkeypatch):
    monkeypatch.setenv("TASK_STORE_BACKEND", "invalid")
    await reset_task_store()

    with pytest.raises(TaskStoreError):
        await task_store_mod._build_task_store()