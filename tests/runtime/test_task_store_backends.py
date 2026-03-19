import pytest

from runtime.queue.task_store import (
    InMemoryTaskStore,
    TaskStoreError,
    _resolve_task_store_backend,
    get_task_store,
    reset_task_store,
)


def test_resolve_task_store_backend_defaults_to_memory(monkeypatch):
    monkeypatch.delenv("TASK_STORE_BACKEND", raising=False)
    assert _resolve_task_store_backend() == "memory"


def test_resolve_task_store_backend_accepts_postgres(monkeypatch):
    monkeypatch.setenv("TASK_STORE_BACKEND", "postgres")
    assert _resolve_task_store_backend() == "postgres"


def test_resolve_task_store_backend_rejects_invalid(monkeypatch):
    monkeypatch.setenv("TASK_STORE_BACKEND", "invalid")
    with pytest.raises(TaskStoreError):
        _resolve_task_store_backend()


@pytest.mark.asyncio
async def test_get_task_store_returns_memory_by_default(monkeypatch):
    monkeypatch.delenv("TASK_STORE_BACKEND", raising=False)
    await reset_task_store()

    store = await get_task_store()
    assert isinstance(store, InMemoryTaskStore)


@pytest.mark.asyncio
async def test_get_task_store_returns_postgres_when_configured(monkeypatch):
    class DummyPostgresStore:
        pass

    dummy_store = DummyPostgresStore()

    monkeypatch.setenv("TASK_STORE_BACKEND", "postgres")
    await reset_task_store()

    import runtime.queue.task_store as task_store_mod
    monkeypatch.setattr(task_store_mod, "_build_postgres_task_store", lambda: dummy_store)

    store = await get_task_store()
    assert store is dummy_store