import pytest

from persistence.repositories.outbox_repository import (
    OutboxRepository,
    OutboxRepositoryConflictError,
    OutboxRepositoryNotFoundError,
)


class FakeScalarResult:
    def __init__(self, items):
        self._items = items

    def scalar_one_or_none(self):
        if not self._items:
            return None
        return self._items[0]

    def scalars(self):
        return self

    def all(self):
        return list(self._items)


class FakeSelect:
    def __init__(self, model):
        self.model = model
        self.filters = []
        self.ordering = []
        self.limit_value = None

    def where(self, *conditions):
        self.filters.extend(conditions)
        return self

    def order_by(self, *ordering):
        self.ordering.extend(ordering)
        return self

    def limit(self, limit_value):
        self.limit_value = limit_value
        return self


class FakeCondition:
    def __init__(self, field_name, op, value):
        self.field_name = field_name
        self.op = op
        self.value = value


class FakeField:
    def __init__(self, name):
        self.name = name

    def __eq__(self, other):
        return FakeCondition(self.name, "eq", other)

    def __le__(self, other):
        return FakeCondition(self.name, "le", other)

    def in_(self, values):
        return FakeCondition(self.name, "in", list(values))

    def asc(self):
        return ("asc", self.name)


class FakeOutboxRecord:
    event_id = FakeField("event_id")
    aggregate_type = FakeField("aggregate_type")
    aggregate_id = FakeField("aggregate_id")
    tenant_id = FakeField("tenant_id")
    event_type = FakeField("event_type")
    queue_name = FakeField("queue_name")
    stream_name = FakeField("stream_name")
    status = FakeField("status")
    available_at = FakeField("available_at")
    created_at = FakeField("created_at")

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
    def __init__(self):
        self._records = {}
        self._next_id = 1

    async def get(self, model, key):
        return self._records.get(key)

    def add(self, record):
        if record.event_id is None:
            record.event_id = self._next_id
            self._next_id += 1
        self._records[record.event_id] = record

    async def flush(self):
        return None

    async def execute(self, stmt):
        records = list(self._records.values())

        for condition in getattr(stmt, "filters", []):
            if condition.op == "eq":
                records = [
                    r for r in records
                    if getattr(r, condition.field_name) == condition.value
                ]
            elif condition.op == "in":
                records = [
                    r for r in records
                    if getattr(r, condition.field_name) in condition.value
                ]
            elif condition.op == "le":
                records = [
                    r for r in records
                    if getattr(r, condition.field_name) <= condition.value
                ]

        for order in reversed(getattr(stmt, "ordering", [])):
            if isinstance(order, tuple) and order[0] == "asc":
                field_name = order[1]
                records.sort(key=lambda r: getattr(r, field_name))

        if getattr(stmt, "limit_value", None) is not None:
            records = records[:stmt.limit_value]

        return FakeScalarResult(records)


@pytest.fixture
def patch_outbox_model_and_select(monkeypatch):
    import persistence.models
    import persistence.repositories.outbox_repository as repo_mod

    monkeypatch.setattr(persistence.models, "RuntimeOutboxEventRecord", FakeOutboxRecord)
    monkeypatch.setattr(repo_mod, "RuntimeOutboxEventRecord", FakeOutboxRecord)
    monkeypatch.setattr(repo_mod, "select", lambda model: FakeSelect(model))


@pytest.mark.asyncio
async def test_create_task_queued_event(patch_outbox_model_and_select):
    session = FakeSession()
    repo = OutboxRepository(session)

    record = await repo.create_task_queued_event(
        tenant_id="tenant-a",
        task_id="task-1",
        queue_name="agent_tasks",
        stream_name="agent_tasks",
        payload_json={"task_id": "task-1"},
    )

    assert record.event_id == 1
    assert record.aggregate_type == "task"
    assert record.aggregate_id == "task-1"
    assert record.tenant_id == "tenant-a"
    assert record.event_type == "task.queued"
    assert record.queue_name == "agent_tasks"
    assert record.stream_name == "agent_tasks"
    assert record.payload_json == {"task_id": "task-1"}
    assert record.status == "pending"
    assert record.publish_attempts == 0
    assert record.last_error_text is None


@pytest.mark.asyncio
async def test_create_task_queued_event_conflict_raises(
    patch_outbox_model_and_select,
):
    session = FakeSession()
    repo = OutboxRepository(session)

    await repo.create_task_queued_event(
        tenant_id="tenant-a",
        task_id="task-1",
        queue_name="agent_tasks",
        stream_name="agent_tasks",
        payload_json={"task_id": "task-1"},
    )

    with pytest.raises(OutboxRepositoryConflictError):
        await repo.create_task_queued_event(
            tenant_id="tenant-a",
            task_id="task-1",
            queue_name="agent_tasks",
            stream_name="agent_tasks",
            payload_json={"task_id": "task-1"},
        )


@pytest.mark.asyncio
async def test_list_publishable_events_returns_pending_and_failed(
    patch_outbox_model_and_select,
):
    session = FakeSession()
    repo = OutboxRepository(session)

    await repo.create_task_queued_event(
        tenant_id="tenant-a",
        task_id="task-1",
        queue_name="agent_tasks",
        stream_name="agent_tasks",
        payload_json={"task_id": "task-1"},
    )
    rec2 = await repo.create_task_queued_event(
        tenant_id="tenant-a",
        task_id="task-2",
        queue_name="generation_tasks",
        stream_name="generation_tasks",
        payload_json={"task_id": "task-2"},
    )
    await repo.mark_failed(event_id=rec2.event_id, error_text="temporary broker error")

    events = await repo.list_publishable_events(limit=10)

    assert len(events) == 2
    assert {e.aggregate_id for e in events} == {"task-1", "task-2"}


@pytest.mark.asyncio
async def test_mark_publishing_and_mark_published(
    patch_outbox_model_and_select,
):
    session = FakeSession()
    repo = OutboxRepository(session)

    record = await repo.create_task_queued_event(
        tenant_id="tenant-a",
        task_id="task-1",
        queue_name="agent_tasks",
        stream_name="agent_tasks",
        payload_json={"task_id": "task-1"},
    )

    publishing = await repo.mark_publishing(event_id=record.event_id)
    assert publishing.status == "publishing"

    published = await repo.mark_published(event_id=record.event_id)
    assert published.status == "published"
    assert published.published_at is not None
    assert published.last_error_text is None


@pytest.mark.asyncio
async def test_mark_failed_increments_attempts(
    patch_outbox_model_and_select,
):
    session = FakeSession()
    repo = OutboxRepository(session)

    record = await repo.create_task_queued_event(
        tenant_id="tenant-a",
        task_id="task-1",
        queue_name="agent_tasks",
        stream_name="agent_tasks",
        payload_json={"task_id": "task-1"},
    )

    failed = await repo.mark_failed(
        event_id=record.event_id,
        error_text="redis unavailable",
    )

    assert failed.status == "failed"
    assert failed.publish_attempts == 1
    assert failed.last_error_text == "redis unavailable"


@pytest.mark.asyncio
async def test_mark_dead_letter_increments_attempts_and_sets_terminal_status(
    patch_outbox_model_and_select,
):
    session = FakeSession()
    repo = OutboxRepository(session)

    record = await repo.create_task_queued_event(
        tenant_id="tenant-a",
        task_id="task-1",
        queue_name="agent_tasks",
        stream_name="agent_tasks",
        payload_json={"task_id": "task-1"},
    )

    dead_lettered = await repo.mark_dead_letter(
        event_id=record.event_id,
        error_text="broker permanently unavailable",
    )

    assert dead_lettered.status == "dead_letter"
    assert dead_lettered.publish_attempts == 1
    assert dead_lettered.last_error_text == "broker permanently unavailable"


@pytest.mark.asyncio
async def test_mark_missing_event_raises_not_found(
    patch_outbox_model_and_select,
):
    session = FakeSession()
    repo = OutboxRepository(session)

    with pytest.raises(OutboxRepositoryNotFoundError):
        await repo.mark_publishing(event_id=999)

    with pytest.raises(OutboxRepositoryNotFoundError):
        await repo.mark_published(event_id=999)

    with pytest.raises(OutboxRepositoryNotFoundError):
        await repo.mark_failed(event_id=999, error_text="missing")

    with pytest.raises(OutboxRepositoryNotFoundError):
        await repo.mark_dead_letter(event_id=999, error_text="missing")