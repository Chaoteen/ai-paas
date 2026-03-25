from __future__ import annotations

from types import SimpleNamespace

import pytest

from runtime.queue.outbox_relay import OutboxRelay


class DummyQueue:
    def __init__(self, should_fail: bool = False):
        self.should_fail = should_fail
        self.published = []

    async def publish_task_payload(self, *, stream_name: str, payload: dict):
        if self.should_fail:
            raise RuntimeError("redis publish failed")
        self.published.append((stream_name, payload))
        return "1-0"


class FakeRepo:
    def __init__(self, event):
        self.event = event
        self.actions = []

    async def list_publishable_events(self, *, limit: int = 100):
        return [self.event]

    async def mark_publishing(self, event_id: int):
        self.actions.append(("publishing", event_id))

    async def mark_published(self, event_id: int):
        self.actions.append(("published", event_id))

    async def mark_failed(self, *, event_id: int, error_text: str, available_at):
        self.actions.append(("failed", event_id, error_text, available_at))

    async def mark_dead_letter(self, *, event_id: int, error_text: str):
        self.actions.append(("dead_letter", event_id, error_text))


class FakeSession:
    def __init__(self, repo):
        self.repo = repo

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def commit(self):
        return None


class FakeSessionFactory:
    def __init__(self, repo):
        self.repo = repo

    def __call__(self):
        return FakeSession(self.repo)


@pytest.mark.asyncio
async def test_outbox_relay_dead_letters_after_max_attempts(monkeypatch):
    event = SimpleNamespace(
        event_id=1,
        stream_name="agent_tasks",
        payload_json={"task_id": "t1"},
        publish_attempts=2,
    )
    repo = FakeRepo(event)

    def fake_repo_ctor(session):
        return repo

    monkeypatch.setattr(
        "runtime.queue.outbox_relay.OutboxRepository",
        fake_repo_ctor,
    )

    relay = OutboxRelay(
        session_factory=FakeSessionFactory(repo),
        queue_client=DummyQueue(should_fail=True),
        retry_backoff_seconds=1,
        max_publish_attempts=3,
    )

    result = await relay.run_once(limit=10)

    assert result.scanned == 1
    assert result.published == 0
    assert result.failed == 0
    assert result.dead_lettered == 1
    assert any(action[0] == "dead_letter" for action in repo.actions)


@pytest.mark.asyncio
async def test_outbox_relay_marks_failed_before_dead_letter_threshold(monkeypatch):
    event = SimpleNamespace(
        event_id=2,
        stream_name="agent_tasks",
        payload_json={"task_id": "t2"},
        publish_attempts=0,
    )
    repo = FakeRepo(event)

    def fake_repo_ctor(session):
        return repo

    monkeypatch.setattr(
        "runtime.queue.outbox_relay.OutboxRepository",
        fake_repo_ctor,
    )

    relay = OutboxRelay(
        session_factory=FakeSessionFactory(repo),
        queue_client=DummyQueue(should_fail=True),
        retry_backoff_seconds=1,
        max_publish_attempts=3,
    )

    result = await relay.run_once(limit=10)

    assert result.scanned == 1
    assert result.published == 0
    assert result.failed == 1
    assert result.dead_lettered == 0
    assert any(action[0] == "failed" for action in repo.actions)