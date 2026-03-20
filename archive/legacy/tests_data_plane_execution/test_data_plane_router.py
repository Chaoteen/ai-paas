import pytest

from data_plane.data_bus import DataBus
from data_plane.envelope import ExecutionEnvelope
from data_plane.repositories.data_event_repository import InMemoryDataEventRepository
from data_plane.result import ExecutionResult
from data_plane.router import DataPlaneRouter


class DummyAgentHandler:
    async def handle(self, envelope):
        return ExecutionResult.success_result(output={"answer": "ok"})


class DummyFailingAgentHandler:
    async def handle(self, envelope):
        return ExecutionResult.error_result("boom")


def build_envelope(target_type: str = "agent") -> ExecutionEnvelope:
    return ExecutionEnvelope(
        envelope_id="env_test_1",
        request_id="req_test_1",
        tenant_id="tenant_1",
        subject={"id": "u1", "tenant_id": "tenant_1"},
        action="prompt.execute",
        resource={"type": "prompt", "id": "default"},
        environment={"region": "default"},
        target_type=target_type,
        target="agent.default",
        payload={"text": "hello"},
        context={},
        created_at=1234567890.0,
    )


@pytest.mark.asyncio
async def test_router_publishes_success_events():
    repo = InMemoryDataEventRepository()
    bus = DataBus(event_repository=repo)

    router = DataPlaneRouter(
        agent_handler=DummyAgentHandler(),
        model_handler=None,
        promptflow_handler=None,
        data_bus=bus,
    )

    result = await router.execute(build_envelope(), timeout_s=3.0)

    assert result.ok is True

    event_types = [e.event_type for e in bus.list_events(envelope_id="env_test_1")]
    assert "task.created" in event_types
    assert "task.dispatched" in event_types
    assert "task.completed" in event_types


@pytest.mark.asyncio
async def test_router_publishes_failed_events():
    repo = InMemoryDataEventRepository()
    bus = DataBus(event_repository=repo)

    router = DataPlaneRouter(
        agent_handler=DummyFailingAgentHandler(),
        model_handler=None,
        promptflow_handler=None,
        data_bus=bus,
    )

    result = await router.execute(build_envelope(), timeout_s=3.0)

    assert result.ok is False

    event_types = [e.event_type for e in bus.list_events(envelope_id="env_test_1")]
    assert "task.created" in event_types
    assert "task.dispatched" in event_types
    assert "task.failed" in event_types