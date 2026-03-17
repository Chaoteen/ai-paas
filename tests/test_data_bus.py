import pytest

from data_plane.data_bus import DataBus


class FakeRepo:
    def __init__(self):
        self.items = []

    async def save(self, event):
        self.items.append(event)
        return event

    async def list_events(self, event_type=None, limit=100):
        data = self.items
        if event_type:
            data = [x for x in data if x.get("event_type") == event_type]
        return list(data[-limit:])[::-1]


class FakeEventBus:
    def __init__(self):
        self.published = []

    def publish(self, envelope):
        self.published.append(envelope)
        return "1-0"

    def ensure_group(self, stream, group_name):
        return None


@pytest.mark.asyncio
async def test_publish_with_task_and_workflow():
    repo = FakeRepo()
    event_bus = FakeEventBus()
    bus = DataBus(repository=repo, event_bus=event_bus)

    event = await bus.publish(
        event_type="task.submitted",
        payload={"required_capability": "translation"},
        source="runtime.api",
        tenant_id="tenant_a",
        correlation_id="corr_001",
        task_id="task_001",
        workflow_id="wf_001",
    )

    assert event["event_type"] == "task.submitted"
    assert event["task_id"] == "task_001"
    assert event["workflow_id"] == "wf_001"
    assert event["tenant_id"] == "tenant_a"
    assert event["correlation_id"] == "corr_001"
    assert "id" in event
    assert len(repo.items) == 1
    assert len(event_bus.published) == 1


@pytest.mark.asyncio
async def test_router_success():
    repo = FakeRepo()
    bus = DataBus(repository=repo, event_bus=None)

    event = await bus.router_success(
        task_id="task_001",
        workflow_id="wf_001",
        route_to="agent_001",
        tenant_id="tenant_a",
        correlation_id="corr_001",
    )

    assert event["event_type"] == "router.success"
    assert event["task_id"] == "task_001"
    assert event["workflow_id"] == "wf_001"
    assert event["payload"]["route_to"] == "agent_001"