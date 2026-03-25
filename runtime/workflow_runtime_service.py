from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Dict
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from persistence.repositories.workflow_execution_event_repository import (
    WorkflowExecutionEventRepository,
)
from persistence.repositories.workflow_execution_repository import (
    WorkflowExecutionRepository,
)
from persistence.repositories.workflow_step_execution_repository import (
    WorkflowStepExecutionRepository,
)
from runtime.queue.task_models import TaskEnvelope
from runtime.workflows.capability_executor import (
    DeterministicWorkflowCapabilityExecutor,
    WorkflowCapabilityExecutionFailed,
    WorkflowCapabilityExecutor,
)
from runtime.workflows.models import (
    WorkflowDefinition,
    WorkflowExecution,
    WorkflowExecutionEvent,
    WorkflowExecutionEventType,
    WorkflowExecutionStatus,
    WorkflowNode,
    WorkflowNodeType,
    WorkflowStepExecution,
    WorkflowStepExecutionStatus,
)
from runtime.workflows.registry import WorkflowRegistry


class WorkflowRuntimeServiceError(Exception):
    """Base exception for workflow runtime service failures."""


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class WorkflowRuntimeService:
    """
    Formal workflow orchestration runtime service.

    Current scope:
    - resolve workflow definition from registry
    - create durable workflow execution record
    - execute sequential capability nodes deterministically
    - persist success and failure state transitions
    - append workflow execution events

    Supported node types:
    - start
    - capability
    - end
    """

    def __init__(
        self,
        *,
        session_factory: Callable[[], AsyncSession],
        registry: WorkflowRegistry,
        capability_executor: WorkflowCapabilityExecutor | None = None,
    ) -> None:
        if session_factory is None:
            raise WorkflowRuntimeServiceError("session_factory must not be None")
        if registry is None:
            raise WorkflowRuntimeServiceError("registry must not be None")

        self._session_factory = session_factory
        self._registry = registry
        self._capability_executor = (
            capability_executor or DeterministicWorkflowCapabilityExecutor()
        )

    async def run(self, task: TaskEnvelope) -> Dict[str, Any]:
        payload = task.payload

        workflow_key = payload.get("workflow_key")
        workflow_version = payload.get("workflow_version")
        workflow_input = payload.get("input", {})
        workflow_context = payload.get("context", {})
        workflow_metadata = payload.get("metadata", {})
        trigger_source = payload.get("trigger_source")

        if not isinstance(workflow_key, str) or not workflow_key.strip():
            raise WorkflowRuntimeServiceError(
                "workflow task payload.workflow_key must be a non-empty string"
            )
        if not isinstance(workflow_version, str) or not workflow_version.strip():
            raise WorkflowRuntimeServiceError(
                "workflow task payload.workflow_version must be a non-empty string"
            )
        if not isinstance(workflow_input, dict):
            raise WorkflowRuntimeServiceError("workflow task payload.input must be a dict")
        if not isinstance(workflow_context, dict):
            raise WorkflowRuntimeServiceError("workflow task payload.context must be a dict")
        if not isinstance(workflow_metadata, dict):
            raise WorkflowRuntimeServiceError("workflow task payload.metadata must be a dict")

        definition = await self._registry.get_definition(
            workflow_key=workflow_key,
            workflow_version=workflow_version,
        )

        nodes_by_id = {node.node_id: node for node in definition.nodes}
        outgoing_edges = defaultdict(list)
        for edge in definition.edges:
            outgoing_edges[edge.source_node_id].append(edge.target_node_id)

        start_node = self._find_single_start_node(definition)

        workflow_execution_id = f"wf-exec-{uuid4().hex}"
        created_step_count = 0
        executed_step_count = 0
        step_outputs: Dict[str, Any] = {}

        frontier = self._resolve_next_nodes(
            source_node_id=start_node.node_id,
            nodes_by_id=nodes_by_id,
            outgoing_edges=outgoing_edges,
        )

        execution = WorkflowExecution(
            workflow_execution_id=workflow_execution_id,
            task_id=task.task_id,
            tenant_id=task.tenant_id,
            workflow_key=definition.workflow_key,
            workflow_version=definition.workflow_version,
            definition_snapshot_json=definition.model_dump(mode="json"),
            status=WorkflowExecutionStatus.RUNNING,
            input_json=deepcopy(workflow_input),
            context_json=deepcopy(workflow_context),
            system_context_json={
                "task_id": task.task_id,
                "queue_name": task.queue_name,
                "correlation_id": task.correlation_id,
                "idempotency_key": task.idempotency_key,
                "trigger_source": trigger_source,
            },
            output_json=None,
            error_text=None,
            active_node_ids=[node.node_id for node in frontier],
            resolved_capabilities_json={
                node.node_id: (
                    node.capability_ref.model_dump(mode="json")
                    if node.capability_ref
                    else {}
                )
                for node in frontier
            },
            governance_json={
                "definition_governance": deepcopy(definition.governance),
                "workflow_metadata": deepcopy(workflow_metadata),
            },
            trace_json={
                "task_id": task.task_id,
                "trigger_source": trigger_source,
            },
            started_at=_utcnow(),
        )

        async with self._session_factory() as session:
            execution_repo = WorkflowExecutionRepository(session)
            step_repo = WorkflowStepExecutionRepository(session)
            event_repo = WorkflowExecutionEventRepository(session)

            await execution_repo.create(execution)

            await event_repo.create(
                WorkflowExecutionEvent(
                    workflow_execution_id=workflow_execution_id,
                    workflow_step_execution_id=None,
                    tenant_id=task.tenant_id,
                    event_type=WorkflowExecutionEventType.EXECUTION_CREATED,
                    payload_json={
                        "workflow_key": definition.workflow_key,
                        "workflow_version": definition.workflow_version,
                        "task_id": task.task_id,
                    },
                )
            )

            await event_repo.create(
                WorkflowExecutionEvent(
                    workflow_execution_id=workflow_execution_id,
                    workflow_step_execution_id=None,
                    tenant_id=task.tenant_id,
                    event_type=WorkflowExecutionEventType.EXECUTION_RUNNING,
                    payload_json={
                        "status": WorkflowExecutionStatus.RUNNING.value,
                        "active_node_ids": list(execution.active_node_ids),
                    },
                )
            )

            try:
                while frontier:
                    next_frontier: list[WorkflowNode] = []

                    for node in frontier:
                        if node.node_type == WorkflowNodeType.END:
                            continue

                        if node.node_type != WorkflowNodeType.CAPABILITY:
                            raise WorkflowRuntimeServiceError(
                                f"Unsupported workflow node_type for sequential runtime: {node.node_type.value}"
                            )

                        created_step_count += 1
                        step_execution_id = f"wf-step-{uuid4().hex}"
                        step_outputs_snapshot = deepcopy(step_outputs)

                        step_execution = WorkflowStepExecution(
                            workflow_step_execution_id=step_execution_id,
                            workflow_execution_id=workflow_execution_id,
                            node_id=node.node_id,
                            node_type=node.node_type.value,
                            capability_ref_json=(
                                node.capability_ref.model_dump(mode="json")
                                if node.capability_ref
                                else {}
                            ),
                            status=WorkflowStepExecutionStatus.READY,
                            attempt_no=1,
                            input_json={
                                "workflow_input": deepcopy(workflow_input),
                                "workflow_context": deepcopy(workflow_context),
                                "step_outputs": step_outputs_snapshot,
                                "node_input_mapping": deepcopy(node.input_mapping),
                            },
                            output_json=None,
                            error_text=None,
                            retry_policy_json=node.retry_policy.model_dump(mode="json"),
                            timeout_policy_json=node.timeout_policy.model_dump(mode="json"),
                            compensation_policy_json=node.compensation_policy.model_dump(mode="json"),
                            trace_json={
                                "workflow_execution_id": workflow_execution_id,
                                "node_id": node.node_id,
                            },
                        )
                        await step_repo.create(step_execution)

                        await event_repo.create(
                            WorkflowExecutionEvent(
                                workflow_execution_id=workflow_execution_id,
                                workflow_step_execution_id=step_execution_id,
                                tenant_id=task.tenant_id,
                                event_type=WorkflowExecutionEventType.STEP_CREATED,
                                payload_json={
                                    "node_id": node.node_id,
                                    "node_type": node.node_type.value,
                                    "status": WorkflowStepExecutionStatus.READY.value,
                                },
                            )
                        )

                        step_execution.status = WorkflowStepExecutionStatus.RUNNING
                        step_execution.started_at = _utcnow()
                        await step_repo.update(step_execution)

                        await event_repo.create(
                            WorkflowExecutionEvent(
                                workflow_execution_id=workflow_execution_id,
                                workflow_step_execution_id=step_execution_id,
                                tenant_id=task.tenant_id,
                                event_type=WorkflowExecutionEventType.STEP_RUNNING,
                                payload_json={
                                    "node_id": node.node_id,
                                    "status": WorkflowStepExecutionStatus.RUNNING.value,
                                },
                            )
                        )

                        try:
                            output = await self._capability_executor.execute(
                                node=node,
                                workflow_input=deepcopy(workflow_input),
                                workflow_context=deepcopy(workflow_context),
                                step_outputs=deepcopy(step_outputs),
                            )
                        except Exception as exc:
                            step_execution.status = WorkflowStepExecutionStatus.FAILED
                            step_execution.error_text = str(exc)
                            step_execution.finished_at = _utcnow()
                            await step_repo.update(step_execution)

                            await event_repo.create(
                                WorkflowExecutionEvent(
                                    workflow_execution_id=workflow_execution_id,
                                    workflow_step_execution_id=step_execution_id,
                                    tenant_id=task.tenant_id,
                                    event_type=WorkflowExecutionEventType.STEP_FAILED,
                                    payload_json={
                                        "node_id": node.node_id,
                                        "status": WorkflowStepExecutionStatus.FAILED.value,
                                        "error": str(exc),
                                    },
                                )
                            )

                            execution.status = WorkflowExecutionStatus.FAILED
                            execution.active_node_ids = []
                            execution.error_text = str(exc)
                            execution.output_json = {
                                "step_outputs": deepcopy(step_outputs),
                                "executed_step_count": executed_step_count,
                                "final_status": WorkflowExecutionStatus.FAILED.value,
                            }
                            execution.finished_at = _utcnow()
                            await execution_repo.update(execution)

                            await event_repo.create(
                                WorkflowExecutionEvent(
                                    workflow_execution_id=workflow_execution_id,
                                    workflow_step_execution_id=None,
                                    tenant_id=task.tenant_id,
                                    event_type=WorkflowExecutionEventType.EXECUTION_FAILED,
                                    payload_json={
                                        "status": WorkflowExecutionStatus.FAILED.value,
                                        "executed_step_count": executed_step_count,
                                        "error": str(exc),
                                    },
                                )
                            )

                            await session.commit()

                            if isinstance(exc, WorkflowCapabilityExecutionFailed):
                                raise
                            raise WorkflowRuntimeServiceError(str(exc)) from exc

                        executed_step_count += 1
                        step_outputs[node.node_id] = deepcopy(output)

                        step_execution.status = WorkflowStepExecutionStatus.SUCCEEDED
                        step_execution.output_json = deepcopy(output)
                        step_execution.finished_at = _utcnow()
                        await step_repo.update(step_execution)

                        await event_repo.create(
                            WorkflowExecutionEvent(
                                workflow_execution_id=workflow_execution_id,
                                workflow_step_execution_id=step_execution_id,
                                tenant_id=task.tenant_id,
                                event_type=WorkflowExecutionEventType.STEP_SUCCEEDED,
                                payload_json={
                                    "node_id": node.node_id,
                                    "status": WorkflowStepExecutionStatus.SUCCEEDED.value,
                                    "output": deepcopy(output),
                                },
                            )
                        )

                        next_nodes = self._resolve_next_nodes(
                            source_node_id=node.node_id,
                            nodes_by_id=nodes_by_id,
                            outgoing_edges=outgoing_edges,
                        )
                        for next_node in next_nodes:
                            if next_node.node_type == WorkflowNodeType.END:
                                continue
                            next_frontier.append(next_node)

                    frontier = next_frontier
                    execution.active_node_ids = [node.node_id for node in frontier]
                    execution.resolved_capabilities_json = {
                        node.node_id: (
                            node.capability_ref.model_dump(mode="json")
                            if node.capability_ref
                            else {}
                        )
                        for node in frontier
                    }
                    await execution_repo.update(execution)

                execution.status = WorkflowExecutionStatus.SUCCEEDED
                execution.active_node_ids = []
                execution.output_json = {
                    "step_outputs": deepcopy(step_outputs),
                    "executed_step_count": executed_step_count,
                    "final_status": WorkflowExecutionStatus.SUCCEEDED.value,
                }
                execution.finished_at = _utcnow()
                await execution_repo.update(execution)

                await event_repo.create(
                    WorkflowExecutionEvent(
                        workflow_execution_id=workflow_execution_id,
                        workflow_step_execution_id=None,
                        tenant_id=task.tenant_id,
                        event_type=WorkflowExecutionEventType.EXECUTION_SUCCEEDED,
                        payload_json={
                            "status": WorkflowExecutionStatus.SUCCEEDED.value,
                            "executed_step_count": executed_step_count,
                            "active_node_ids": [],
                        },
                    )
                )

                await session.commit()

            except WorkflowCapabilityExecutionFailed:
                raise

        return {
            "status": "accepted",
            "workflow_execution_id": workflow_execution_id,
            "workflow_key": definition.workflow_key,
            "workflow_version": definition.workflow_version,
            "workflow_status": WorkflowExecutionStatus.SUCCEEDED.value,
            "active_node_ids": [],
            "created_step_count": created_step_count,
            "executed_step_count": executed_step_count,
            "step_outputs": deepcopy(step_outputs),
        }

    @staticmethod
    def _find_single_start_node(definition: WorkflowDefinition) -> WorkflowNode:
        start_nodes = [
            node for node in definition.nodes if node.node_type == WorkflowNodeType.START
        ]
        if len(start_nodes) != 1:
            raise WorkflowRuntimeServiceError(
                f"Workflow definition must contain exactly one start node, got {len(start_nodes)}"
            )
        return start_nodes[0]

    @staticmethod
    def _resolve_next_nodes(
        source_node_id: str,
        nodes_by_id: Dict[str, WorkflowNode],
        outgoing_edges: Dict[str, list[str]],
    ) -> list[WorkflowNode]:
        next_node_ids = outgoing_edges.get(source_node_id, [])
        next_nodes: list[WorkflowNode] = []

        for node_id in next_node_ids:
            node = nodes_by_id.get(node_id)
            if node is None:
                raise WorkflowRuntimeServiceError(
                    f"Workflow definition references unknown node_id: {node_id}"
                )
            next_nodes.append(node)

        return next_nodes