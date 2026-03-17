import pytest

from runtime.state_store import InMemoryRuntimeStateStore
from runtime.workflow_state import (
    TASK_STATUS_COMPLETED,
    TASK_STATUS_EXECUTING,
    TASK_STATUS_ROUTED,
    TASK_STATUS_SUBMITTED,
)


@pytest.mark.asyncio
async def test_state_store_creates_task_once() -> None:
    store = InMemoryRuntimeStateStore()

    first = await store.create_task(
        task_id="task-001",
        tenant_id="tenant-a",
        workflow_id="wf-001",
        correlation_id="corr-001",
        input_payload={"text": "hello"},
        metadata={"source": "test"},
    )
    second = await store.create_task(
        task_id="task-001",
        tenant_id="tenant-a",
    )

    assert first is second
    assert first.status == TASK_STATUS_SUBMITTED
    assert first.workflow_id == "wf-001"
    assert first.input_payload["text"] == "hello"
    assert first.metadata["source"] == "test"


@pytest.mark.asyncio
async def test_state_store_task_transitions_happy_path() -> None:
    store = InMemoryRuntimeStateStore()

    await store.create_task(
        task_id="task-002",
        tenant_id="tenant-a",
        input_payload={"text": "hello"},
    )

    routed = await store.transition_task(
        task_id="task-002",
        new_status=TASK_STATUS_ROUTED,
        event_type="router.success",
        selected_agent_id="agent-001",
    )
    assert routed.status == TASK_STATUS_ROUTED
    assert routed.selected_agent_id == "agent-001"
    assert routed.last_event_type == "router.success"

    executing = await store.transition_task(
        task_id="task-002",
        new_status=TASK_STATUS_EXECUTING,
        event_type="task.executing",
        selected_skill="echo",
    )
    assert executing.status == TASK_STATUS_EXECUTING
    assert executing.selected_skill == "echo"

    completed = await store.transition_task(
        task_id="task-002",
        new_status=TASK_STATUS_COMPLETED,
        event_type="task.completed",
        output_payload={"result": "ok"},
    )
    assert completed.status == TASK_STATUS_COMPLETED
    assert completed.output_payload["result"] == "ok"
    assert completed.completed_at is not None


@pytest.mark.asyncio
async def test_state_store_rejects_illegal_transition() -> None:
    store = InMemoryRuntimeStateStore()

    await store.create_task(
        task_id="task-003",
        tenant_id="tenant-a",
    )

    with pytest.raises(ValueError):
        await store.transition_task(
            task_id="task-003",
            new_status=TASK_STATUS_COMPLETED,
            event_type="task.completed",
        )


@pytest.mark.asyncio
async def test_state_store_workflow_collects_tasks() -> None:
    store = InMemoryRuntimeStateStore()

    await store.create_task(
        task_id="task-004",
        tenant_id="tenant-a",
        workflow_id="wf-xyz",
    )
    await store.create_task(
        task_id="task-005",
        tenant_id="tenant-a",
        workflow_id="wf-xyz",
    )

    workflow = await store.get_workflow("wf-xyz")
    assert workflow is not None
    assert workflow.workflow_id == "wf-xyz"
    assert sorted(workflow.task_ids) == ["task-004", "task-005"]