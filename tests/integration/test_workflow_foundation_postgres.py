from __future__ import annotations

import os
import uuid

import asyncpg
import pytest
import pytest_asyncio

from persistence.db import Database
from persistence.settings import PostgresSettings
from persistence.repositories.workflow_definition_repository import (
    WorkflowDefinitionRepository,
)
from persistence.repositories.workflow_execution_event_repository import (
    WorkflowExecutionEventRepository,
)
from persistence.repositories.workflow_execution_repository import (
    WorkflowExecutionRepository,
)
from persistence.repositories.workflow_step_execution_repository import (
    WorkflowStepExecutionRepository,
)
from runtime.workflows.models import (
    CapabilityKind,
    CapabilityRef,
    WorkflowDefinition,
    WorkflowDefinitionStatus,
    WorkflowEdge,
    WorkflowExecution,
    WorkflowExecutionEvent,
    WorkflowExecutionEventType,
    WorkflowExecutionStatus,
    WorkflowNode,
    WorkflowNodeType,
    WorkflowStepExecution,
    WorkflowStepExecutionStatus,
)

pytestmark = pytest.mark.asyncio


def _require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        pytest.skip(f"{name} is required for workflow Postgres integration test")
    return value


def _postgres_dsn() -> dict[str, object]:
    return {
        "host": _require_env("POSTGRES_HOST"),
        "port": int(os.getenv("POSTGRES_PORT", "5432").strip()),
        "database": _require_env("POSTGRES_DB"),
        "user": _require_env("POSTGRES_USER"),
        "password": _require_env("POSTGRES_PASSWORD"),
    }


async def _truncate_workflow_tables() -> None:
    conn = await asyncpg.connect(**_postgres_dsn())
    try:
        await conn.execute(
            """
            TRUNCATE TABLE
                workflow_execution_events,
                workflow_step_executions,
                workflow_executions,
                workflow_definitions
            RESTART IDENTITY
            """
        )
    finally:
        await conn.close()


@pytest_asyncio.fixture(autouse=True)
async def _clean_workflow_tables():
    await _truncate_workflow_tables()
    yield
    await _truncate_workflow_tables()


def _build_definition(
    *,
    workflow_key: str,
    workflow_version: str,
) -> WorkflowDefinition:
    return WorkflowDefinition(
        workflow_key=workflow_key,
        workflow_version=workflow_version,
        display_name="Pricing Quote Flow",
        status=WorkflowDefinitionStatus.ACTIVE,
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
        checksum="workflow-checksum-001",
        created_by="integration-test",
        updated_by="integration-test",
    )


def _build_execution(
    *,
    workflow_execution_id: str,
    task_id: str,
    workflow_key: str,
    workflow_version: str,
) -> WorkflowExecution:
    return WorkflowExecution(
        workflow_execution_id=workflow_execution_id,
        task_id=task_id,
        tenant_id="dev",
        workflow_key=workflow_key,
        workflow_version=workflow_version,
        definition_snapshot_json={
            "workflow_key": workflow_key,
            "workflow_version": workflow_version,
            "display_name": "Pricing Quote Flow",
        },
        status=WorkflowExecutionStatus.RUNNING,
        input_json={"customer_name": "Acme"},
        context_json={"channel": "api"},
        system_context_json={"request_id": "req-001"},
        output_json=None,
        error_text=None,
        active_node_ids=["draft_quote"],
        resolved_capabilities_json={
            "draft_quote": {
                "kind": "agent",
                "key": "sales.quote.drafter",
                "version": "1.2.0",
            }
        },
        governance_json={"tenant_scoped": True},
        trace_json={"trace_id": "trace-001"},
    )


def _build_step_execution(
    *,
    workflow_step_execution_id: str,
    workflow_execution_id: str,
) -> WorkflowStepExecution:
    return WorkflowStepExecution(
        workflow_step_execution_id=workflow_step_execution_id,
        workflow_execution_id=workflow_execution_id,
        node_id="draft_quote",
        node_type="capability",
        capability_ref_json={
            "kind": "agent",
            "key": "sales.quote.drafter",
            "version": "1.2.0",
        },
        status=WorkflowStepExecutionStatus.RUNNING,
        attempt_no=1,
        input_json={"customer_name": "Acme"},
        output_json=None,
        error_text=None,
        retry_policy_json={"max_attempts": 3, "backoff_seconds": 1},
        timeout_policy_json={"timeout_seconds": 60},
        compensation_policy_json={"enabled": False},
        trace_json={"span_id": "span-001"},
    )


async def test_workflow_definition_repository_round_trip_postgres() -> None:
    database = Database(PostgresSettings())
    session_factory = database.session_factory  # noqa: SLF001

    try:
        workflow_key = f"pricing.quote.flow.{uuid.uuid4().hex[:8]}"
        workflow_version = "1.0.0"
        definition = _build_definition(
            workflow_key=workflow_key,
            workflow_version=workflow_version,
        )

        async with session_factory() as session:
            repo = WorkflowDefinitionRepository(session)
            await repo.create(definition)
            await session.commit()

        async with session_factory() as session:
            repo = WorkflowDefinitionRepository(session)

            loaded = await repo.get(
                workflow_key=workflow_key,
                workflow_version=workflow_version,
            )
            assert loaded is not None
            assert loaded.workflow_key == workflow_key
            assert loaded.workflow_version == workflow_version
            assert loaded.status == WorkflowDefinitionStatus.ACTIVE
            assert loaded.display_name == "Pricing Quote Flow"
            assert len(loaded.nodes) == 3
            assert loaded.nodes[1].node_id == "draft_quote"
            assert loaded.nodes[1].capability_ref is not None
            assert loaded.nodes[1].capability_ref.key == "sales.quote.drafter"

            active = await repo.get_active(workflow_key=workflow_key)
            assert active is not None
            assert active.workflow_key == workflow_key
            assert active.workflow_version == workflow_version

            versions = await repo.list_versions(workflow_key=workflow_key)
            assert len(versions) == 1
            assert versions[0].workflow_version == workflow_version
    finally:
        await database.dispose()


async def test_workflow_execution_step_event_round_trip_postgres() -> None:
    database = Database(PostgresSettings())
    session_factory = database.session_factory  # noqa: SLF001 phase19去掉了_session前面的_

    try:
        workflow_key = f"pricing.quote.flow.{uuid.uuid4().hex[:8]}"
        workflow_version = "1.0.0"
        workflow_execution_id = f"wf-exec-{uuid.uuid4().hex}"
        workflow_step_execution_id = f"wf-step-{uuid.uuid4().hex}"
        task_id = f"wf-task-{uuid.uuid4().hex}"

        definition = _build_definition(
            workflow_key=workflow_key,
            workflow_version=workflow_version,
        )
        execution = _build_execution(
            workflow_execution_id=workflow_execution_id,
            task_id=task_id,
            workflow_key=workflow_key,
            workflow_version=workflow_version,
        )
        step_execution = _build_step_execution(
            workflow_step_execution_id=workflow_step_execution_id,
            workflow_execution_id=workflow_execution_id,
        )
        event = WorkflowExecutionEvent(
            workflow_execution_id=workflow_execution_id,
            workflow_step_execution_id=workflow_step_execution_id,
            tenant_id="dev",
            event_type=WorkflowExecutionEventType.STEP_RUNNING,
            payload_json={
                "node_id": "draft_quote",
                "status": "running",
            },
        )

        async with session_factory() as session:
            definition_repo = WorkflowDefinitionRepository(session)
            execution_repo = WorkflowExecutionRepository(session)
            step_repo = WorkflowStepExecutionRepository(session)
            event_repo = WorkflowExecutionEventRepository(session)

            await definition_repo.create(definition)
            await execution_repo.create(execution)
            await step_repo.create(step_execution)
            await event_repo.create(event)
            await session.commit()

        async with session_factory() as session:
            execution_repo = WorkflowExecutionRepository(session)
            step_repo = WorkflowStepExecutionRepository(session)
            event_repo = WorkflowExecutionEventRepository(session)

            loaded_execution = await execution_repo.get(workflow_execution_id)
            assert loaded_execution is not None
            assert loaded_execution.workflow_execution_id == workflow_execution_id
            assert loaded_execution.task_id == task_id
            assert loaded_execution.workflow_key == workflow_key
            assert loaded_execution.workflow_version == workflow_version
            assert loaded_execution.status == WorkflowExecutionStatus.RUNNING
            assert loaded_execution.active_node_ids == ["draft_quote"]
            assert loaded_execution.input_json["customer_name"] == "Acme"

            loaded_by_task = await execution_repo.get_by_task_id(task_id)
            assert loaded_by_task is not None
            assert loaded_by_task.workflow_execution_id == workflow_execution_id

            tenant_items = await execution_repo.list_by_tenant(tenant_id="dev")
            assert len(tenant_items) == 1
            assert tenant_items[0].workflow_execution_id == workflow_execution_id

            step_items = await step_repo.list_by_execution(
                workflow_execution_id=workflow_execution_id
            )
            assert len(step_items) == 1
            assert step_items[0].workflow_step_execution_id == workflow_step_execution_id
            assert step_items[0].node_id == "draft_quote"
            assert step_items[0].status == WorkflowStepExecutionStatus.RUNNING
            assert step_items[0].retry_policy_json["max_attempts"] == 3

            event_items = await event_repo.list_by_execution(
                workflow_execution_id=workflow_execution_id
            )
            assert len(event_items) == 1
            assert event_items[0].workflow_step_execution_id == workflow_step_execution_id
            assert event_items[0].event_type == WorkflowExecutionEventType.STEP_RUNNING
            assert event_items[0].payload_json["node_id"] == "draft_quote"
    finally:
        await database.dispose()