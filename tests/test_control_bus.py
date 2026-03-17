import asyncio
import pytest

from control_plane.control_bus import ControlBus, InMemoryControlEventRepository


class HangingEventBus:
    def publish(self, envelope):
        import time
        time.sleep(10)


@pytest.mark.asyncio
async def test_control_bus_publish_does_not_block_when_event_bus_hangs():
    repo = InMemoryControlEventRepository()
    bus = ControlBus(repository=repo, event_bus=HangingEventBus())

    result = await bus.publish(
        event_type="agent.registered",
        tenant_id="tenant-a",
        agent_id="agent-001",
        payload={"name": "agent-001"},
    )

    assert result["event_type"] == "agent.registered"

    items = await bus.list_events(limit=10)
    assert len(items) == 1
    assert items[0]["event_type"] == "agent.registered"