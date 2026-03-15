import pytest

from data_plane.repositories.postgres_data_event_repository import (
    PostgresDataEventRepository,
)


@pytest.mark.asyncio
async def test_append_and_list_data_events(pg_async_db):
    repo = PostgresDataEventRepository(pg_async_db)

    await repo.append({
        "id": "de-001",
        "task_id": "task-001",
        "execution_id": "exec-001",
        "event_type": "task.created",
        "tenant_id": "tenant-a",
        "payload": {"input": "hello"},
    })
    await repo.append({
        "id": "de-002",
        "task_id": "task-001",
        "execution_id": "exec-001",
        "event_type": "task.completed",
        "tenant_id": "tenant-a",
        "payload": {"output": "world"},
    })

    events = await repo.list(limit=10)
    assert len(events) == 2

    created_events = await repo.list(event_type="task.created")
    assert len(created_events) == 1
    assert created_events[0]["id"] == "de-001"

    task_events = await repo.list(task_id="task-001")
    assert len(task_events) == 2

    execution_events = await repo.list(execution_id="exec-001")
    assert len(execution_events) == 2