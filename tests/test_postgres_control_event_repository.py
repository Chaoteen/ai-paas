import pytest

from control_plane.repositories.postgres_control_event_repository import (
    PostgresControlEventRepository,
)


@pytest.mark.asyncio
async def test_append_and_list_control_events(pg_async_db):
    repo = PostgresControlEventRepository(pg_async_db)

    await repo.append({
        "id": "ce-001",
        "event_type": "agent.registered",
        "agent_id": "agent-001",
        "tenant_id": "tenant-a",
        "payload": {"source": "bootstrap"},
    })
    await repo.append({
        "id": "ce-002",
        "event_type": "agent.heartbeat",
        "agent_id": "agent-001",
        "tenant_id": "tenant-a",
        "payload": {"healthy": True},
    })

    events = await repo.list(limit=10)
    assert len(events) == 2

    registered_events = await repo.list(event_type="agent.registered")
    assert len(registered_events) == 1
    assert registered_events[0]["id"] == "ce-001"

    agent_events = await repo.list(agent_id="agent-001")
    assert len(agent_events) == 2