import pytest

from runtime.queue.postgres_task_store import PostgresTaskStore
from runtime.queue.task_models import AgentTaskPayload, TaskEnvelope
from runtime.queue.task_store import (
    TaskStoreConflictError,
    TaskStoreNotFoundError,
)


class FakeSession:
    def __init__(self) -> None:
        self._records = {}
        self._committed = False
        self._rolled_back = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def commit(self) -> None:
        self._committed = True

    async def rollback(self) -> None:
        self._rolled_back = True

    async def flush(self) -> None:
        return None

    async def get(self, model, key):
        return self._records.get(key)

    def add(self, record) -> None:
        self._records[record.task_id] = record

    async def delete(self, record) -> None:
        self._records.pop(record.task_id, None)


class FakeTaskRecord:
    def __init__(self, **kwargs):
        self.task_id = kwargs["task_id"]
        self.tenant_id = kwargs["tenant_id"]
        self.task_type = kwargs["task_type"]
        self.queue_name = kwargs["queue_name"]
        self.status = kwargs["status"]
        self.payload_json = kwargs["payload_json"]
        self.result_json = kwargs["result_json"]
        self.error_text = kwargs["error_text"]
        self.retry_count = kwargs["retry_count"]
        self.correlation_id = kwargs["correlation_id"]
        self.idempotency_key = kwargs["idempotency_key"]
        self.created_at = kwargs["created_at"]
        self.queued_at = kwargs["queued_at"]
        self.started_at = kwargs["started_at"]
        self.finished_at = kwargs["finished_at"]
        self.updated_at = kwargs["updated_at"]


@pytest.fixture
def patch_runtime_task_record(monkeypatch):
    import persistence.models
    import persistence.repositories.task_repository as repo_mod

    monkeypatch.setattr(persistence.models, "RuntimeTaskRecord", FakeTaskRecord)
    monkeypatch.setattr(repo_mod, "RuntimeTaskRecord", FakeTaskRecord)


def build_task() -> TaskEnvelope:
    return TaskEnvelope.for_agent(
        tenant_id="tenant-a",
        payload=AgentTaskPayload(
            prompt="hello",
            model="test-model",
        ),
        queue_name="agent_tasks",
        correlation_id="corr-1",
        idempotency_key="idem-1",
    )


@pytest.mark.asyncio
async def test_postgres_task_store_create_and_get(patch_runtime_task_record) -> None:
    session = FakeSession()
    store = PostgresTaskStore(session_factory=lambda: session)

    task = build_task()
    await store.create(task)

    loaded = await store.get(task.task_id)
    assert loaded is not None
    assert loaded.task_id == task.task_id
    assert loaded.tenant_id == "tenant-a"
    assert loaded.task_type.value == "agent"
    assert loaded.queue_name == "agent_tasks"
    assert loaded.payload["prompt"] == "hello"


@pytest.mark.asyncio
async def test_postgres_task_store_create_conflict_raises(
    patch_runtime_task_record,
) -> None:
    session = FakeSession()
    store = PostgresTaskStore(session_factory=lambda: session)

    task = build_task()
    await store.create(task)

    with pytest.raises(TaskStoreConflictError):
        await store.create(task)


@pytest.mark.asyncio
async def test_postgres_task_store_put_updates_existing(
    patch_runtime_task_record,
) -> None:
    session = FakeSession()
    store = PostgresTaskStore(session_factory=lambda: session)

    task = build_task()
    await store.put(task)

    task.mark_queued()
    await store.put(task)

    loaded = await store.get(task.task_id)
    assert loaded is not None
    assert loaded.status.value == "queued"


@pytest.mark.asyncio
async def test_postgres_task_store_update_missing_raises(
    patch_runtime_task_record,
) -> None:
    session = FakeSession()
    store = PostgresTaskStore(session_factory=lambda: session)

    task = build_task()

    with pytest.raises(TaskStoreNotFoundError):
        await store.update(task)


@pytest.mark.asyncio
async def test_postgres_task_store_exists_and_delete(
    patch_runtime_task_record,
) -> None:
    session = FakeSession()
    store = PostgresTaskStore(session_factory=lambda: session)

    task = build_task()
    assert await store.exists(task.task_id) is False

    await store.create(task)
    assert await store.exists(task.task_id) is True

    await store.delete(task.task_id)
    assert await store.exists(task.task_id) is False