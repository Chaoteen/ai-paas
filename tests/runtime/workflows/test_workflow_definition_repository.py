import pytest

from persistence.repositories.workflow_definition_repository import (
    WorkflowDefinitionRepository,
    WorkflowDefinitionRepositoryConflictError,
    WorkflowDefinitionRepositoryNotFoundError,
)
from runtime.workflows.models import (
    CapabilityKind,
    CapabilityRef,
    WorkflowDefinition,
    WorkflowDefinitionStatus,
    WorkflowEdge,
    WorkflowNode,
    WorkflowNodeType,
)


class FakeWorkflowDefinitionRecord:
    def __init__(self, **kwargs):
        self.workflow_key = kwargs["workflow_key"]
        self.workflow_version = kwargs["workflow_version"]
        self.display_name = kwargs["display_name"]
        self.status = kwargs["status"]
        self.schema_json = kwargs["schema_json"]
        self.input_schema_json = kwargs["input_schema_json"]
        self.output_schema_json = kwargs["output_schema_json"]
        self.policies_json = kwargs["policies_json"]
        self.governance_json = kwargs["governance_json"]
        self.metadata_json = kwargs["metadata_json"]
        self.checksum = kwargs["checksum"]
        self.created_by = kwargs["created_by"]
        self.updated_by = kwargs["updated_by"]
        self.created_at = kwargs["created_at"]
        self.updated_at = kwargs["updated_at"]


class _FakeScalarResult:
    def __init__(self, records):
        self._records = list(records)

    def first(self):
        return self._records[0] if self._records else None

    def all(self):
        return list(self._records)


class _FakeExecuteResult:
    def __init__(self, records):
        self._records = list(records)

    def scalars(self):
        return _FakeScalarResult(self._records)


class FakeSession:
    def __init__(self) -> None:
        self._definition_records = {}

    async def get(self, model, key):
        if isinstance(key, dict):
            compound_key = (key["workflow_key"], key["workflow_version"])
            return self._definition_records.get(compound_key)
        return None

    def add(self, record) -> None:
        key = (record.workflow_key, record.workflow_version)
        self._definition_records[key] = record

    async def flush(self) -> None:
        return None

    async def execute(self, stmt):
        records = list(self._definition_records.values())

        whereclause = getattr(stmt, "whereclause", None)
        if whereclause is not None:
            text = str(whereclause)

            if "workflow_definitions.workflow_key" in text:
                workflow_key = whereclause.right.value
                records = [
                    r for r in records if r.workflow_key == workflow_key
                ]

            if "workflow_definitions.status" in text:
                active_value = "active"
                records = [
                    r for r in records if r.status == active_value
                ]

        if "ORDER BY workflow_definitions.updated_at DESC" in str(stmt):
            records = sorted(records, key=lambda r: r.updated_at, reverse=True)
        elif "ORDER BY workflow_definitions.created_at ASC" in str(stmt):
            records = sorted(records, key=lambda r: r.created_at)

        return _FakeExecuteResult(records)


@pytest.fixture
def patch_workflow_definition_record(monkeypatch):
    import persistence.models
    import persistence.repositories.workflow_definition_repository as repo_mod

    monkeypatch.setattr(
        persistence.models,
        "WorkflowDefinitionRecord",
        FakeWorkflowDefinitionRecord,
    )
    monkeypatch.setattr(
        repo_mod,
        "WorkflowDefinitionRecord",
        FakeWorkflowDefinitionRecord,
    )


def build_definition(
    *,
    workflow_key: str = "pricing.quote.flow",
    workflow_version: str = "1.0.0",
    status: WorkflowDefinitionStatus = WorkflowDefinitionStatus.DRAFT,
) -> WorkflowDefinition:
    return WorkflowDefinition(
        workflow_key=workflow_key,
        workflow_version=workflow_version,
        display_name="Pricing Quote Flow",
        status=status,
        input_schema={"type": "object"},
        output_schema={"type": "object"},
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
        policies={"retry": "node-level"},
        governance={"tenant_scoped": True},
        metadata={"owner": "workflow-team"},
        checksum="abc123",
        created_by="tester",
        updated_by="tester",
    )


@pytest.mark.asyncio
async def test_create_and_get_definition(patch_workflow_definition_record) -> None:
    session = FakeSession()
    repo = WorkflowDefinitionRepository(session)

    definition = build_definition()
    await repo.create(definition)

    loaded = await repo.get(
        workflow_key="pricing.quote.flow",
        workflow_version="1.0.0",
    )

    assert loaded is not None
    assert loaded.workflow_key == "pricing.quote.flow"
    assert loaded.workflow_version == "1.0.0"
    assert loaded.display_name == "Pricing Quote Flow"
    assert loaded.nodes[1].capability_ref is not None
    assert loaded.nodes[1].capability_ref.key == "sales.quote.drafter"


@pytest.mark.asyncio
async def test_create_duplicate_definition_raises_conflict(
    patch_workflow_definition_record,
) -> None:
    session = FakeSession()
    repo = WorkflowDefinitionRepository(session)

    definition = build_definition()
    await repo.create(definition)

    with pytest.raises(WorkflowDefinitionRepositoryConflictError):
        await repo.create(definition)


@pytest.mark.asyncio
async def test_update_definition_changes_status_and_schema(
    patch_workflow_definition_record,
) -> None:
    session = FakeSession()
    repo = WorkflowDefinitionRepository(session)

    definition = build_definition()
    await repo.create(definition)

    updated = build_definition(status=WorkflowDefinitionStatus.ACTIVE)
    updated.display_name = "Pricing Quote Flow Active"
    updated.metadata["release"] = "ga"

    await repo.update(updated)

    loaded = await repo.get(
        workflow_key="pricing.quote.flow",
        workflow_version="1.0.0",
    )
    assert loaded is not None
    assert loaded.status == WorkflowDefinitionStatus.ACTIVE
    assert loaded.display_name == "Pricing Quote Flow Active"
    assert loaded.metadata["release"] == "ga"


@pytest.mark.asyncio
async def test_update_missing_definition_raises_not_found(
    patch_workflow_definition_record,
) -> None:
    session = FakeSession()
    repo = WorkflowDefinitionRepository(session)

    definition = build_definition()

    with pytest.raises(WorkflowDefinitionRepositoryNotFoundError):
        await repo.update(definition)


@pytest.mark.asyncio
async def test_get_active_definition_returns_only_active_version(
    patch_workflow_definition_record,
) -> None:
    session = FakeSession()
    repo = WorkflowDefinitionRepository(session)

    await repo.create(
        build_definition(
            workflow_version="1.0.0",
            status=WorkflowDefinitionStatus.DRAFT,
        )
    )
    await repo.create(
        build_definition(
            workflow_version="1.1.0",
            status=WorkflowDefinitionStatus.ACTIVE,
        )
    )

    loaded = await repo.get_active(workflow_key="pricing.quote.flow")
    assert loaded is not None
    assert loaded.workflow_version == "1.1.0"
    assert loaded.status == WorkflowDefinitionStatus.ACTIVE