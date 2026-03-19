import pytest

from runtime.queue.task_models import AgentTaskPayload, TaskEnvelope
from runtime.queue.task_submission_service import (
    TaskSubmissionConflictError,
    TaskSubmissionService,
)


class FakeField:
    def __init__(self, name):
        self.name = name

    def __eq__(self, other):
        return FakeCondition(self.name, "eq", other)


class FakeCondition:
    def __init__(self, field_name, op, value):
        self.field_name = field_name
        self.op = op
        self.value = value


class FakeScalarResult:
    def __init__(self, items):
        self._items = items

    def scalar_one_or_none(self):
        if not self._items:
            return None
        return self._items[0]


class FakeSelect:
    def __init__(self, model):
        self.model = model
        self.filters = []

    def where(self, *conditions):
        self.filters.extend(conditions)
        return self


class FakeTaskRecord:
    task_id = FakeField("task_id")
    tenant_id = FakeField("tenant_id")
    task_type = FakeField("task_type")
    queue_name = FakeField("queue_name")
    status = FakeField("status")
    correlation_id = FakeField("correlation_id")
    idempotency_key = FakeField("idempotency_key")

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


class FakeOutboxRecord:
    event_id = FakeField("event_id")
    aggregate_type = FakeField("aggregate_type")
    aggregate_id = FakeField("aggregate_id")
    tenant_id = FakeField("tenant_id")
    event_type = FakeField("event_type")
    queue_name = FakeField("queue_name")
    stream_name = FakeField("stream_name")
    status = FakeField("status")

    def __init__(self, **kwargs):
        self.event_id = kwargs.get("event_id")
        self.aggregate_type = kwargs["aggregate_type"]
        self.aggregate_id = kwargs["aggregate_id"]
        self.tenant_id = kwargs["tenant_id"]
        self.event_type = kwargs["event_type"]
        self.queue_name = kwargs["queue_name"]
        self.stream_name = kwargs["stream_name"]
        self.payload_json = kwargs["payload_json"]
        self.status = kwargs["status"]
        self.publish_attempts = kwargs["publish_attempts"]
        self.last_error_text = kwargs["last_error_text"]
        self.available_at = kwargs["available_at"]
        self.published_at = kwargs["published_at"]
        self.created_at = kwargs["created_at"]
        self.updated_at = kwargs["updated_at"]


class FakeSession:
    def __init__(self) -> None:
        self._task_records = {}
        self._outbox_records = {}
        self._next_outbox_id = 1
        self.committed = False
        self.rolled_back = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True

    async def flush(self) -> None:
        return None

    async def get(self, model, key):
        model_name = getattr(model, "__name__", "")
        if model_name == "FakeTaskRecord":
            return self._task_records.get(key)
        if model_name == "FakeOutboxRecord":
            return self._outbox_records.get(key)
        return None

    def add(self, record) -> None:
        if isinstance(record, FakeTaskRecord):
            self._task_records[record.task_id] = record
            return

        if isinstance(record, FakeOutboxRecord):
            if record.event_id is None:
                record.event_id = self._next_outbox_id
                self._next_outbox_id += 1
            self._outbox_records[record.event_id] = record
            return

        raise TypeError(f"Unsupported record type: {type(record)!r}")

    async def execute(self, stmt):
        model_name = getattr(stmt.model, "__name__", "")

        if model_name == "FakeTaskRecord":
            records = list(self._task_records.values())
        elif model_name == "FakeOutboxRecord":
            records = list(self._outbox_records.values())
        else:
            records = []

        for condition in getattr(stmt, "filters", []):
            if condition.op == "eq":
                records = [
                    r for r in records
                    if getattr(r, condition.field_name) == condition.value
                ]

        return FakeScalarResult(records)


@pytest.fixture
def patch_repositories(monkeypatch):
    import persistence.models
    import persistence.repositories.task_repository as task_repo_mod
    import persistence.repositories.outbox_repository as outbox_repo_mod

    monkeypatch.setattr(persistence.models, "RuntimeTaskRecord", FakeTaskRecord)
    monkeypatch.setattr(persistence.models, "RuntimeOutboxEventRecord", FakeOutboxRecord)

    monkeypatch.setattr(task_repo_mod, "RuntimeTaskRecord", FakeTaskRecord)
    monkeypatch.setattr(outbox_repo_mod, "RuntimeOutboxEventRecord", FakeOutboxRecord)

    monkeypatch.setattr(task_repo_mod, "select", lambda model: FakeSelect(model))
    monkeypatch.setattr(outbox_repo_mod, "select", lambda model: FakeSelect(model))


def build_task(idempotency_key: str | None = "idem-1") -> TaskEnvelope:
    return TaskEnvelope.for_agent(
        tenant_id="tenant-a",
        payload=AgentTaskPayload(
            prompt="hello",
            model="test-model",
        ),
        queue_name="agent_tasks",
        correlation_id="corr-1",
        idempotency_key=idempotency_key,
    )


@pytest.mark.asyncio
async def test_submit_task_persists_task_and_outbox(patch_repositories) -> None:
    session = FakeSession()
    service = TaskSubmissionService(session_factory=lambda: session)

    task = build_task()

    result = await service.submit_task(
        task=task,
        stream_name="agent_tasks",
    )

    assert result.task_id == task.task_id
    assert result.queue_name == "agent_tasks"
    assert result.stream_name == "agent_tasks"
    assert result.outbox_event_id == 1
    assert result.status == "queued"

    assert session.committed is True
    assert session.rolled_back is False

    stored_task = session._task_records[task.task_id]
    assert stored_task.status == "queued"

    stored_outbox = session._outbox_records[1]
    assert stored_outbox.aggregate_id == task.task_id
    assert stored_outbox.event_type == "task.queued"
    assert stored_outbox.status == "pending"
    assert stored_outbox.stream_name == "agent_tasks"


@pytest.mark.asyncio
async def test_submit_task_marks_task_queued_before_persist(
    patch_repositories,
) -> None:
    session = FakeSession()
    service = TaskSubmissionService(session_factory=lambda: session)

    task = build_task()
    assert task.status.value == "created"

    await service.submit_task(task=task, stream_name="agent_tasks")

    assert task.status.value == "queued"
    assert task.queued_at is not None


@pytest.mark.asyncio
async def test_submit_task_idempotency_conflict_raises(
    patch_repositories,
) -> None:
    session = FakeSession()
    service = TaskSubmissionService(session_factory=lambda: session)

    task1 = build_task(idempotency_key="idem-conflict")
    task2 = build_task(idempotency_key="idem-conflict")

    await service.submit_task(task=task1, stream_name="agent_tasks")

    with pytest.raises(TaskSubmissionConflictError):
        await service.submit_task(task=task2, stream_name="agent_tasks")

    assert session.rolled_back is True


@pytest.mark.asyncio
async def test_submit_task_without_idempotency_allows_distinct_tasks(
    patch_repositories,
) -> None:
    session = FakeSession()
    service = TaskSubmissionService(session_factory=lambda: session)

    task1 = build_task(idempotency_key=None)
    task2 = build_task(idempotency_key=None)

    result1 = await service.submit_task(task=task1, stream_name="agent_tasks")
    result2 = await service.submit_task(task=task2, stream_name="agent_tasks")

    assert result1.task_id != result2.task_id
    assert len(session._task_records) == 2
    assert len(session._outbox_records) == 2


@pytest.mark.asyncio
async def test_submit_task_reuses_queue_name_as_default_stream(
    patch_repositories,
) -> None:
    session = FakeSession()
    service = TaskSubmissionService(session_factory=lambda: session)

    task = build_task()

    result = await service.submit_task(task=task)

    assert result.stream_name == "agent_tasks"
    stored_outbox = session._outbox_records[result.outbox_event_id]
    assert stored_outbox.stream_name == "agent_tasks"