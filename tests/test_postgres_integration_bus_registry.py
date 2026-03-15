import pytest

from control_plane.agent_registry import AgentRegistry
from control_plane.control_bus import ControlBus
from data_plane.data_bus import DataBus

from control_plane.repositories.postgres_agent_repository import PostgresAgentRepository
from control_plane.repositories.postgres_control_event_repository import (
    PostgresControlEventRepository,
)
from data_plane.repositories.postgres_data_event_repository import (
    PostgresDataEventRepository,
)


@pytest.mark.asyncio
async def test_agent_registry_with_postgres_and_control_bus(pg_async_db):
    agent_repo = PostgresAgentRepository(pg_async_db)
    control_repo = PostgresControlEventRepository(pg_async_db)
    control_bus = ControlBus(repository=control_repo)
    registry = AgentRegistry(repository=agent_repo, control_bus=control_bus)

    agent = await registry.register_agent({
        "id": "agent-pg-001",
        "name": "postgres-agent",
        "version": "1.0.0",
        "status": "active",
        "tenant_id": "tenant-a",
        "capabilities": {"mode": "worker"},
        "metadata": {"source": "test"},
        "endpoint": "http://localhost:9001",
    })

    assert agent["id"] == "agent-pg-001"

    all_agents = await registry.list_agents()
    assert len(all_agents) == 1

    events = await control_bus.list_events()
    assert len(events) == 1
    assert events[0]["event_type"] == "agent.registered"
    assert events[0]["agent_id"] == "agent-pg-001"


@pytest.mark.asyncio
async def test_agent_heartbeat_publishes_control_event(pg_async_db):
    agent_repo = PostgresAgentRepository(pg_async_db)
    control_repo = PostgresControlEventRepository(pg_async_db)
    control_bus = ControlBus(repository=control_repo)
    registry = AgentRegistry(repository=agent_repo, control_bus=control_bus)

    await registry.register_agent({
        "id": "agent-pg-002",
        "name": "heartbeat-agent",
        "version": "1.0.0",
        "status": "active",
        "tenant_id": "tenant-a",
        "capabilities": {},
        "metadata": {},
        "endpoint": "http://localhost:9002",
    })

    ok = await registry.heartbeat("agent-pg-002")
    assert ok is True

    heartbeat_events = await control_bus.list_events(event_type="agent.heartbeat")
    assert len(heartbeat_events) == 1
    assert heartbeat_events[0]["agent_id"] == "agent-pg-002"


@pytest.mark.asyncio
async def test_data_bus_with_postgres_repository(pg_async_db):
    data_repo = PostgresDataEventRepository(pg_async_db)
    data_bus = DataBus(repository=data_repo)

    await data_bus.publish(
        event_type="task.created",
        task_id="task-pg-001",
        execution_id="exec-pg-001",
        tenant_id="tenant-a",
        payload={"input": "hello"},
    )

    await data_bus.publish(
        event_type="task.completed",
        task_id="task-pg-001",
        execution_id="exec-pg-001",
        tenant_id="tenant-a",
        payload={"output": "world"},
    )

    all_events = await data_bus.list_events()
    assert len(all_events) == 2

    created_events = await data_bus.list_events(event_type="task.created")
    assert len(created_events) == 1
    assert created_events[0]["task_id"] == "task-pg-001"