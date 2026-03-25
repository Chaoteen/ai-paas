import pytest

from persistence.repositories.workflow_execution_event_repository import (
    WorkflowExecutionEventRepository,
)
from persistence.repositories.workflow_execution_repository import (
    WorkflowExecutionRepository,
    WorkflowExecutionRepositoryConflictError,
    WorkflowExecutionRepositoryNotFoundError,
)
from persistence.repositories.workflow_step_execution_repository import (
    WorkflowStepExecutionRepository,
)
from runtime.workflows.models import (
    WorkflowExecution,
    WorkflowExecutionEvent,
    WorkflowExecutionEventType,
    WorkflowExecutionStatus,
    WorkflowStepExecution,
    WorkflowStepExecutionStatus,
)


class FakeWorkflowExecutionRecord:
    def __init__(self, **kwargs):
        self.workflow_execution_id = kwargs["workflow_execution_id"]
        self.task_id = kwargs["task_id"]
        self.tenant_id = kwargs["tenant_id"]
        self.workflow_key = kwargs["workflow_key"]
        self.workflow_version = kwargs["workflow_version"]
        self.status = kwargs["status"]
        self.definition_snapshot_json = kwargs["definition_snapshot_json"]
        self.input_json = kwargs["input_json"]
        self.context_json = kwargs["context_json"]
        self.system_context_json = kwargs["system_context_json"]
        self.output_json = kwargs["output_json"]
        self.error_text = kwargs["error_text"]
        self.active_node_ids = kwargs["active_node_ids"]
        self.resolved_capabilities_json = kwargs["resolved_capabilities_json"]
        self.governance_json = kwargs["governance_json"]
        self.trace_json = kwargs["trace_json"]
        self.created_at = kwargs["created_at"]
        self.started_at = kwargs["started_at"]
        self.finished_at = kwargs["finished_at"]
        self.updated_at = kwargs["updated_at"]


class FakeWorkflowStepExecutionRecord:
    def __init__(self, **kwargs):
        self.workflow_step_execution_id = kwargs["workflow_step_execution_id"]
        self.workflow_execution_id = kwargs["workflow_execution_id"]
        self.node_id = kwargs["node_id"]
        self.node_type = kwargs["node_type"]
        self.capability_ref_json = kwargs["capability_ref_json"]
        self.status = kwargs["status"]
        self.attempt_no = kwargs["attempt_no"]
        self.input_json = kwargs["input_json"]
        self.output_json = kwargs["output_json"]
        self.error_text = kwargs["error_text"]
        self.retry_policy_json = kwargs["retry_policy_json"]
        self.timeout_policy_json = kwargs["timeout_policy_json"]
        self.compensation_policy_json = kwargs["compensation_policy_json"]
        self.trace_json = kwargs["trace_json"]
        self.created_at = kwargs["created_at"]
        self.started_at = kwargs["started_at"]
        self.finished_at = kwargs["finished_at"]
        self.updated_at = kwargs["updated_at"]


class FakeWorkflowExecutionEventRecord:
    _auto_id = 0

    def __init__(self, **kwargs):
        type(self)._auto_id += 1
        self.workflow_execution_event_id = type(self)._auto_id
        self.workflow_execution_id = kwargs["workflow_execution_id"]
        self.workflow_step_execution_id = kwargs["workflow_step_execution_id"]
        self.tenant_id = kwargs["tenant_id"]
        self.event_type = kwargs["event_type"]
        self.payload_json = kwargs["payload_json"]
        self.created_at = kwargs["created_at"]


class _FakeScalarResult:
    def __init__(self, records):
        self._records = list(records)

    def all(self):
        return list(self._records)

    def first(self):
        return self._records[0] if self._records else None


class _FakeExecuteResult:
    def __init__(self, records, scalar_one_or_none=None):
        self._records = list(records)
        self._scalar_one_or_none = scalar_one_or_none

    def scalars(self):
        return _FakeScalarResult(self._records)

    def scalar_one_or_none(self):
        return self._scalar_one_or_none


class FakeSession:
    def __init__(self) -> None:
        self._execution_records = {}
        self._step_records = {}
        self._event_records = []

    async def get(self, model, key):
        model_name = getattr(model, "__name__", str(model))
        if model_name == "FakeWorkflowExecutionRecord":
            return self._execution_records.get(key)
        if model_name == "FakeWorkflowStepExecutionRecord":
            return self._step_records.get(key)
        return None

    def add(self, record) -> None:
        if hasattr(record, "workflow_execution_id") and hasattr(record, "task_id"):
            self._execution_records[record.workflow_execution_id] = record
            return
        if hasattr(record, "workflow_step_execution_id"):
            self._step_records[record.workflow_step_execution_id] = record
            return
        self._event_records.append(record)

    async def flush(self) -> None:
        return None

    async def execute(self, stmt):
        text = str(stmt)

        if "FROM workflow_executions" in text and "task_id" in text:
            for record in self._execution_records.values():
                if f"= :task_id_1" in text:
                    return _FakeExecuteResult([], scalar_one_or_none=record)
            return _FakeExecuteResult([], scalar_one_or_none=None)

        if "FROM workflow_executions" in text:
            records = list(self._execution_records.values())
            if "tenant_id" in text:
                records = sorted(records, key=lambda r: r.created_at, reverse=True)
            return _FakeExecuteResult(records)

        if "FROM workflow_step_executions" in text:
            records = sorted(
                self._step_records.values(),
                key=lambda r: (r.created_at, r.attempt_no),
            )
            return _FakeExecuteResult(records)

        if "FROM workflow_execution_events" in text:
            records = sorted(self._event_records, key=lambda r: r.created_at)
            return _FakeExecuteResult(records)

        return _FakeExecuteResult([])


@pytest.fixture
def patch_workflow_records(monkeypatch):
    import persistence.models
    import persistence.repositories.workflow_execution_repository as execution_repo_mod
    import persistence.repositories.workflow_step_execution_repository as step_repo_mod
    import persistence.repositories.workflow_execution_event_repository as event_repo_mod

    monkeypatch.setattr(
        persistence.models,
        "WorkflowExecutionRecord",
        FakeWorkflowExecutionRecord,
    )
    monkeypatch.setattr(
        persistence.models,
        "WorkflowStepExecutionRecord",
        FakeWorkflowStepExecutionRecord,
    )
    monkeypatch.setattr(
        persistence.models,
        "WorkflowExecutionEventRecord",
        FakeWorkflowExecutionEventRecord,
    )

    monkeypatch.setattr(
        execution_repo_mod,
        "WorkflowExecutionRecord",
        FakeWorkflowExecutionRecord,
    )
    monkeypatch.setattr(
        step_repo_mod,
        "WorkflowStepExecutionRecord",
        FakeWorkflowStepExecutionRecord,
    )
    monkeypatch.setattr(
        event_repo_mod,
        "WorkflowExecutionEventRecord",
        FakeWorkflowExecutionEventRecord,
    )


def build_execution() -> WorkflowExecution:
    return WorkflowExecution(
        workflow_execution_id="wf-exec-001",
        task_id="task-001",
        tenant_id="tenant-a",
        workflow_key="pricing.quote.flow",
        workflow_version="1.0.0",
        definition_snapshot_json={"workflow_key": "pricing.quote.flow"},
        status=WorkflowExecutionStatus.CREATED,
        input_json={"customer_name": "Acme"},
        context_json={"channel": "api"},
        system_context_json={"request_id": "req-001"},
        active_node_ids=["start"],
        resolved_capabilities_json={"draft_quote": {"kind": "agent"}},
        governance_json={"tenant_scoped": True},
        trace_json={"trace_id": "trace-001"},
    )


def build_step_execution() -> WorkflowStepExecution:
    return WorkflowStepExecution(
        workflow_step_execution_id="wf-step-001",
        workflow_execution_id="wf-exec-001",
        node_id="draft_quote",
        node_type="capability",
        capability_ref_json={
            "kind": "agent",
            "key": "sales.quote.drafter",
            "version": "1.2.0",
        },
        status=WorkflowStepExecutionStatus.CREATED,
        attempt_no=1,
        input_json={"customer_name": "Acme"},
        retry_policy_json={"max_attempts": 3},
        timeout_policy_json={"timeout_seconds": 60},
        compensation_policy_json={"enabled": False},
        trace_json={"span_id": "span-001"},
    )


@pytest.mark.asyncio
async def test_create_and_get_workflow_execution(patch_workflow_records) -> None:
    session = FakeSession()
    repo = WorkflowExecutionRepository(session)

    execution = build_execution()
    await repo.create(execution)

    loaded = await repo.get("wf-exec-001")
    assert loaded is not None
    assert loaded.workflow_execution_id == "wf-exec-001"
    assert loaded.task_id == "task-001"
    assert loaded.workflow_key == "pricing.quote.flow"
    assert loaded.status == WorkflowExecutionStatus.CREATED


@pytest.mark.asyncio
async def test_duplicate_workflow_execution_raises_conflict(
    patch_workflow_records,
) -> None:
    session = FakeSession()
    repo = WorkflowExecutionRepository(session)

    execution = build_execution()
    await repo.create(execution)

    with pytest.raises(WorkflowExecutionRepositoryConflictError):
        await repo.create(execution)


@pytest.mark.asyncio
async def test_update_missing_workflow_execution_raises_not_found(
    patch_workflow_records,
) -> None:
    session = FakeSession()
    repo = WorkflowExecutionRepository(session)

    execution = build_execution()

    with pytest.raises(WorkflowExecutionRepositoryNotFoundError):
        await repo.update(execution)


@pytest.mark.asyncio
async def test_step_execution_and_event_append_to_execution(
    patch_workflow_records,
) -> None:
    session = FakeSession()

    execution_repo = WorkflowExecutionRepository(session)
    step_repo = WorkflowStepExecutionRepository(session)
    event_repo = WorkflowExecutionEventRepository(session)

    execution = build_execution()
    await execution_repo.create(execution)

    step_execution = build_step_execution()
    await step_repo.create(step_execution)

    await event_repo.create(
        WorkflowExecutionEvent(
            workflow_execution_id="wf-exec-001",
            workflow_step_execution_id="wf-step-001",
            tenant_id="tenant-a",
            event_type=WorkflowExecutionEventType.STEP_CREATED,
            payload_json={"node_id": "draft_quote"},
        )
    )

    steps = await step_repo.list_by_execution(workflow_execution_id="wf-exec-001")
    events = await event_repo.list_by_execution(workflow_execution_id="wf-exec-001")

    assert len(steps) == 1
    assert steps[0].node_id == "draft_quote"
    assert steps[0].status == WorkflowStepExecutionStatus.CREATED

    assert len(events) == 1
    assert events[0].event_type == WorkflowExecutionEventType.STEP_CREATED
    assert events[0].payload_json["node_id"] == "draft_quote"