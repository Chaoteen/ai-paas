import pytest

from data_plane.router_worker import RouterWorker


class FakeAgentRegistry:
    def __init__(self, agents):
        self._agents = agents

    async def list_agents(self, tenant_id=None):
        if tenant_id is None:
            return self._agents
        return [x for x in self._agents if x.get("tenant_id") == tenant_id]


class FakeDataBus:
    def __init__(self):
        self.success_events = []
        self.failed_events = []

    async def router_success(self, **kwargs):
        self.success_events.append(kwargs)
        return kwargs

    async def router_failed(self, **kwargs):
        self.failed_events.append(kwargs)
        return kwargs


class FakeEnvelope:
    def __init__(self, **kwargs):
        self.event_type = kwargs.get("event_type", "task.submitted")
        self.task_id = kwargs.get("task_id")
        self.workflow_id = kwargs.get("workflow_id")
        self.tenant_id = kwargs.get("tenant_id")
        self.correlation_id = kwargs.get("correlation_id")
        self.payload = kwargs.get("payload", {})


class FakeEventBus:
    def ensure_group(self, stream, group_name):
        return None

    def consume(self, **kwargs):
        return []

    def ack(self, stream, group_name, message_id):
        return 1

    def dead_letter(self, **kwargs):
        return "1-0"


@pytest.mark.asyncio
async def test_router_worker_success():
    registry = FakeAgentRegistry(
        [
            {
                "id": "agent_001",
                "name": "translator-agent",
                "tenant_id": "tenant_a",
                "status": "healthy",
                "capabilities": {"skills": ["translation", "analysis"]},
                "heartbeat_at": "2026-03-16T10:00:00+00:00",
            }
        ]
    )
    data_bus = FakeDataBus()
    worker = RouterWorker(
        agent_registry=registry,
        data_bus=data_bus,
        event_bus=FakeEventBus(),
    )

    envelope = FakeEnvelope(
        task_id="task_001",
        workflow_id="wf_001",
        tenant_id="tenant_a",
        correlation_id="corr_001",
        payload={"required_capability": "translation"},
    )

    await worker._handle_envelope(envelope)

    assert len(data_bus.success_events) == 1
    assert data_bus.success_events[0]["task_id"] == "task_001"
    assert data_bus.success_events[0]["route_to"] == "agent_001"


@pytest.mark.asyncio
async def test_router_worker_failed_when_no_capability():
    registry = FakeAgentRegistry(
        [
            {
                "id": "agent_001",
                "name": "analysis-agent",
                "tenant_id": "tenant_a",
                "status": "healthy",
                "capabilities": {"skills": ["analysis"]},
                "heartbeat_at": "2026-03-16T10:00:00+00:00",
            }
        ]
    )
    data_bus = FakeDataBus()
    worker = RouterWorker(
        agent_registry=registry,
        data_bus=data_bus,
        event_bus=FakeEventBus(),
    )

    envelope = FakeEnvelope(
        task_id="task_001",
        workflow_id="wf_001",
        tenant_id="tenant_a",
        correlation_id="corr_001",
        payload={"required_capability": "translation"},
    )

    await worker._handle_envelope(envelope)

    assert len(data_bus.failed_events) == 1
    assert data_bus.failed_events[0]["error"] == "NO_ELIGIBLE_AGENT"


@pytest.mark.asyncio
async def test_router_worker_failed_when_missing_required_capability():
    registry = FakeAgentRegistry([])
    data_bus = FakeDataBus()
    worker = RouterWorker(
        agent_registry=registry,
        data_bus=data_bus,
        event_bus=FakeEventBus(),
    )

    envelope = FakeEnvelope(
        task_id="task_001",
        workflow_id="wf_001",
        tenant_id="tenant_a",
        correlation_id="corr_001",
        payload={},
    )

    await worker._handle_envelope(envelope)

    assert len(data_bus.failed_events) == 1
    assert data_bus.failed_events[0]["error"] == "REQUIRED_CAPABILITY_MISSING"