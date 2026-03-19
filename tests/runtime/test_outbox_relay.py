import pytest

from runtime.queue.outbox_relay import OutboxRelay


class FakeOutboxRecord:
    def __init__(self, event_id, stream_name, payload_json):
        self.event_id = event_id
        self.stream_name = stream_name
        self.payload_json = payload_json


class FakeSession:
    def __init__(self, records):
        self.records = {r.event_id: r for r in records}
        self.committed = False
        self.rolled_back = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def commit(self):
        self.committed = True

    async def rollback(self):
        self.rolled_back = True


class FakeSessionFactory:
    def __init__(self, records):
        self.records = records

    def __call__(self):
        return FakeSession(self.records)


class FakeQueue:
    def __init__(self, fail=False):
        self.fail = fail
        self.published = []

    async def publish_task_payload(self, *, stream_name, payload):
        if self.fail:
            raise RuntimeError("redis unavailable")
        self.published.append((stream_name, payload))
        return "msg-1"


@pytest.fixture
def patch_outbox_repo(monkeypatch):
    import runtime.queue.outbox_relay as relay_mod

    class FakeOutboxRepository:
        def __init__(self, session):
            self._session = session

        async def list_publishable_events(self, *, limit=100):
            return list(self._session.records.values())[:limit]

        async def mark_publishing(self, *, event_id):
            return self._session.records[event_id]

        async def mark_published(self, *, event_id):
            return self._session.records[event_id]

        async def mark_failed(self, *, event_id, error_text, next_available_at=None):
            return self._session.records[event_id]

    monkeypatch.setattr(relay_mod, "OutboxRepository", FakeOutboxRepository)


@pytest.mark.asyncio
async def test_outbox_relay_publishes_events(patch_outbox_repo):
    records = [
        FakeOutboxRecord(
            event_id=1,
            stream_name="agent_tasks",
            payload_json={"task_id": "task-1"},
        ),
        FakeOutboxRecord(
            event_id=2,
            stream_name="generation_tasks",
            payload_json={"task_id": "task-2"},
        ),
    ]

    relay = OutboxRelay(
        session_factory=FakeSessionFactory(records),
        queue_client=FakeQueue(),
    )

    result = await relay.run_once(limit=10)

    assert result.scanned == 2
    assert result.published == 2
    assert result.failed == 0


@pytest.mark.asyncio
async def test_outbox_relay_marks_failures(patch_outbox_repo):
    records = [
        FakeOutboxRecord(
            event_id=1,
            stream_name="agent_tasks",
            payload_json={"task_id": "task-1"},
        )
    ]

    relay = OutboxRelay(
        session_factory=FakeSessionFactory(records),
        queue_client=FakeQueue(fail=True),
        retry_backoff_seconds=3,
    )

    result = await relay.run_once(limit=10)

    assert result.scanned == 1
    assert result.published == 0
    assert result.failed == 1