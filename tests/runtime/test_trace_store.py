import pytest

from runtime.trace_store import InMemoryTraceStore


@pytest.mark.asyncio
async def test_trace_store_appends_and_reads_by_task():
    store = InMemoryTraceStore()

    await store.append_event(
        {
            "id": "evt-001",
            "event_type": "task.submitted",
            "task_id": "task-001",
            "workflow_id": "wf-001",
            "tenant_id": "tenant-a",
            "correlation_id": "corr-001",
            "source": "runtime.api",
            "payload": {"x": 1},
            "occurred_at": "2026-01-01T00:00:00+00:00",
        }
    )
    await store.append_event(
        {
            "id": "evt-002",
            "event_type": "task.completed",
            "task_id": "task-001",
            "workflow_id": "wf-001",
            "tenant_id": "tenant-a",
            "correlation_id": "corr-001",
            "source": "runtime.worker",
            "payload": {"y": 2},
            "occurred_at": "2026-01-01T00:00:01+00:00",
        }
    )

    items = await store.get_trace("task-001")
    assert len(items) == 2
    assert items[0].event_type == "task.submitted"
    assert items[1].event_type == "task.completed"