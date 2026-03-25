import pytest

from runtime.queue.task_models import TaskEnvelope, WorkflowTaskPayload
from runtime.workflow_runtime_service import (
    WorkflowRuntimeService,
    WorkflowRuntimeServiceError,
)
from runtime.workflows.capability_executor import WorkflowCapabilityExecutionFailed
from runtime.workflows.models import (
    CapabilityKind,
    CapabilityRef,
    WorkflowDefinition,
    WorkflowDefinitionStatus,
    WorkflowEdge,
    WorkflowExecutionStatus,
    WorkflowNode,
    WorkflowNodeType,
    WorkflowStepExecutionStatus,
)


class FakeSession:
    def __init__(self):
        self.committed = False
        self.rolled_back = False

    async def commit(self):
        self.committed = True

    async def rollback(self):
        self.rolled_back = True

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class FakeExecutionRepo:
    created = []
    updated = []

    def __init__(self, session):
        self.session = session

    async def create(self, execution):
        self.__class__.created.append(execution)
        return execution

    async def update(self, execution):
        self.__class__.updated.append(execution)
        return execution


class FakeStepRepo:
    created = []
    updated = []

    def __init__(self, session):
        self.session = session

    async def create(self, step_execution):
        self.__class__.created.append(step_execution)
        return step_execution

    async def update(self, step_execution):
        self.__class__.updated.append(step_execution)
        return step_execution


class FakeEventRepo:
    created = []

    def __init__(self, session):
        self.session = session

    async def create(self, event):
        self.__class__.created.append(event)
        return event


class FakeRegistry:
    def __init__(self, definition):
        self.definition = definition

    async def get_definition(self, *, workflow_key: str, workflow_version: str | None = None):
        return self.definition


class FakeCapabilityExecutor:
    async def execute(self, *, node, workflow_input, workflow_context, step_outputs):
        return {
            "node_id": node.node_id,
            "status": "succeeded",
            "workflow_input": workflow_input,
            "workflow_context": workflow_context,
            "previous_step_outputs": step_outputs,
            "message": "fake capability executed",
        }


class FailingCapabilityExecutor:
    async def execute(self, *, node, workflow_input, workflow_context, step_outputs):
        raise WorkflowCapabilityExecutionFailed(
            f"Injected failure for node: {node.node_id}"
        )


def _build_definition():
    return WorkflowDefinition(
        workflow_key="pricing.quote.flow",
        workflow_version="1.0.0",
        display_name="Pricing Quote Flow",
        status=WorkflowDefinitionStatus.ACTIVE,
        nodes=[
            WorkflowNode(
                node_id="start",
                node_type=WorkflowNodeType.START,
                name="Start",
            ),
            WorkflowNode(
                node_id="draft_quote",
                node_type=WorkflowNodeType.CAPABILITY,
                name="Draft Quote",
                capability_ref=CapabilityRef(
                    kind=CapabilityKind.AGENT,
                    key="sales.quote.drafter",
                    version="1.2.0",
                ),
            ),
            WorkflowNode(
                node_id="end",
                node_type=WorkflowNodeType.END,
                name="End",
            ),
        ],
        edges=[
            WorkflowEdge(
                edge_id="e1",
                source_node_id="start",
                target_node_id="draft_quote",
            ),
            WorkflowEdge(
                edge_id="e2",
                source_node_id="draft_quote",
                target_node_id="end",
            ),
        ],
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        policies={"retry": "node-level"},
        governance={"tenant_scoped": True},
        metadata={"owner": "workflow-team"},
    )


@pytest.mark.asyncio
async def test_workflow_runtime_service_executes_sequential_capability(monkeypatch):
    import runtime.workflow_runtime_service as service_mod

    FakeExecutionRepo.created = []
    FakeExecutionRepo.updated = []
    FakeStepRepo.created = []
    FakeStepRepo.updated = []
    FakeEventRepo.created = []

    monkeypatch.setattr(service_mod, "WorkflowExecutionRepository", FakeExecutionRepo)
    monkeypatch.setattr(service_mod, "WorkflowStepExecutionRepository", FakeStepRepo)
    monkeypatch.setattr(service_mod, "WorkflowExecutionEventRepository", FakeEventRepo)

    def session_factory():
        return FakeSession()

    service = WorkflowRuntimeService(
        session_factory=session_factory,
        registry=FakeRegistry(_build_definition()),
        capability_executor=FakeCapabilityExecutor(),
    )

    task = TaskEnvelope.for_workflow(
        tenant_id="dev",
        payload=WorkflowTaskPayload(
            workflow_key="pricing.quote.flow",
            workflow_version="1.0.0",
            input={"customer_name": "Acme"},
            context={"channel": "api"},
            metadata={"trace_id": "trace-001"},
            trigger_source="api",
        ),
    )

    result = await service.run(task)

    assert result["status"] == "accepted"
    assert result["workflow_key"] == "pricing.quote.flow"
    assert result["workflow_version"] == "1.0.0"
    assert result["workflow_status"] == WorkflowExecutionStatus.SUCCEEDED.value
    assert result["active_node_ids"] == []
    assert result["created_step_count"] == 1
    assert result["executed_step_count"] == 1
    assert "draft_quote" in result["step_outputs"]

    assert len(FakeExecutionRepo.created) == 1
    assert FakeExecutionRepo.created[0].task_id == task.task_id

    assert len(FakeExecutionRepo.updated) >= 1
    assert FakeExecutionRepo.updated[-1].status == WorkflowExecutionStatus.SUCCEEDED
    assert FakeExecutionRepo.updated[-1].active_node_ids == []

    assert len(FakeStepRepo.created) == 1
    assert FakeStepRepo.created[0].node_id == "draft_quote"

    assert len(FakeStepRepo.updated) >= 2
    assert FakeStepRepo.updated[-1].status == WorkflowStepExecutionStatus.SUCCEEDED
    assert FakeStepRepo.updated[-1].output_json is not None

    event_types = [item.event_type.value for item in FakeEventRepo.created]
    assert event_types == [
        "execution.created",
        "execution.running",
        "step.created",
        "step.running",
        "step.succeeded",
        "execution.succeeded",
    ]


@pytest.mark.asyncio
async def test_workflow_runtime_service_marks_failure_path(monkeypatch):
    import runtime.workflow_runtime_service as service_mod

    FakeExecutionRepo.created = []
    FakeExecutionRepo.updated = []
    FakeStepRepo.created = []
    FakeStepRepo.updated = []
    FakeEventRepo.created = []

    monkeypatch.setattr(service_mod, "WorkflowExecutionRepository", FakeExecutionRepo)
    monkeypatch.setattr(service_mod, "WorkflowStepExecutionRepository", FakeStepRepo)
    monkeypatch.setattr(service_mod, "WorkflowExecutionEventRepository", FakeEventRepo)

    def session_factory():
        return FakeSession()

    service = WorkflowRuntimeService(
        session_factory=session_factory,
        registry=FakeRegistry(_build_definition()),
        capability_executor=FailingCapabilityExecutor(),
    )

    task = TaskEnvelope.for_workflow(
        tenant_id="dev",
        payload=WorkflowTaskPayload(
            workflow_key="pricing.quote.flow",
            workflow_version="1.0.0",
            input={"customer_name": "Acme"},
            context={"channel": "api"},
            metadata={"trace_id": "trace-001"},
            trigger_source="api",
        ),
    )

    with pytest.raises(WorkflowCapabilityExecutionFailed):
        await service.run(task)

    assert len(FakeExecutionRepo.created) == 1
    assert len(FakeExecutionRepo.updated) >= 1
    assert FakeExecutionRepo.updated[-1].status == WorkflowExecutionStatus.FAILED
    assert FakeExecutionRepo.updated[-1].active_node_ids == []
    assert FakeExecutionRepo.updated[-1].error_text is not None

    assert len(FakeStepRepo.created) == 1
    assert len(FakeStepRepo.updated) >= 2
    assert FakeStepRepo.updated[-1].status == WorkflowStepExecutionStatus.FAILED
    assert FakeStepRepo.updated[-1].error_text is not None

    event_types = [item.event_type.value for item in FakeEventRepo.created]
    assert event_types == [
        "execution.created",
        "execution.running",
        "step.created",
        "step.running",
        "step.failed",
        "execution.failed",
    ]


@pytest.mark.asyncio
async def test_workflow_runtime_service_requires_single_start_node():
    definition = _build_definition()
    definition.nodes = [
        node for node in definition.nodes if node.node_type != WorkflowNodeType.START
    ]

    def session_factory():
        return FakeSession()

    service = WorkflowRuntimeService(
        session_factory=session_factory,
        registry=FakeRegistry(definition),
        capability_executor=FakeCapabilityExecutor(),
    )

    task = TaskEnvelope.for_workflow(
        tenant_id="dev",
        payload=WorkflowTaskPayload(
            workflow_key="pricing.quote.flow",
            workflow_version="1.0.0",
            input={},
            context={},
            metadata={},
        ),
    )

    with pytest.raises(WorkflowRuntimeServiceError):
        await service.run(task)