from datetime import datetime, timezone

import pytest

from control_plane.repositories.postgres_agent_repository import PostgresAgentRepository


@pytest.mark.asyncio
async def test_save_and_get_agent(pg_async_db):
    repo = PostgresAgentRepository(pg_async_db)

    saved = await repo.save({
        "id": "agent-001",
        "name": "demo-agent",
        "version": "1.0.0",
        "status": "active",
        "tenant_id": "tenant-a",
        "capabilities": {"tools": ["search", "summarize"]},
        "metadata": {"owner": "platform-team"},
        "heartbeat_at": datetime.now(timezone.utc),
    })

    assert saved["id"] == "agent-001"
    assert saved["name"] == "demo-agent"
    assert saved["status"] == "active"

    found = await repo.get("agent-001")
    assert found is not None
    assert found["tenant_id"] == "tenant-a"
    assert found["capabilities"]["tools"] == ["search", "summarize"]


@pytest.mark.asyncio
async def test_list_agents(pg_async_db):
    repo = PostgresAgentRepository(pg_async_db)

    await repo.save({
        "id": "agent-001",
        "name": "agent-1",
        "version": "1.0.0",
        "status": "active",
        "tenant_id": "tenant-a",
        "capabilities": {},
        "metadata": {},
    })
    await repo.save({
        "id": "agent-002",
        "name": "agent-2",
        "version": "1.0.0",
        "status": "inactive",
        "tenant_id": "tenant-b",
        "capabilities": {},
        "metadata": {},
    })

    all_agents = await repo.list()
    assert len(all_agents) == 2

    tenant_a_agents = await repo.list(tenant_id="tenant-a")
    assert len(tenant_a_agents) == 1
    assert tenant_a_agents[0]["id"] == "agent-001"


@pytest.mark.asyncio
async def test_update_status_and_touch_heartbeat(pg_async_db):
    repo = PostgresAgentRepository(pg_async_db)

    await repo.save({
        "id": "agent-003",
        "name": "agent-3",
        "version": "1.0.0",
        "status": "starting",
        "tenant_id": "tenant-a",
        "capabilities": {},
        "metadata": {},
    })

    ok = await repo.update_status("agent-003", "active")
    assert ok is True

    ok = await repo.touch_heartbeat("agent-003")
    assert ok is True

    agent = await repo.get("agent-003")
    assert agent["status"] == "active"
    assert agent["heartbeat_at"] is not None


@pytest.mark.asyncio
async def test_delete_agent(pg_async_db):
    repo = PostgresAgentRepository(pg_async_db)

    await repo.save({
        "id": "agent-004",
        "name": "agent-4",
        "version": "1.0.0",
        "status": "active",
        "tenant_id": "tenant-a",
        "capabilities": {},
        "metadata": {},
    })

    deleted = await repo.delete("agent-004")
    assert deleted is True

    found = await repo.get("agent-004")
    assert found is None