from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Protocol

from runtime.workflows.models import WorkflowNode


class WorkflowCapabilityExecutorError(Exception):
    """Base exception for workflow capability execution failures."""


class WorkflowCapabilityExecutionFailed(WorkflowCapabilityExecutorError):
    """Raised when a workflow capability execution fails."""


class WorkflowCapabilityExecutor(Protocol):
    async def execute(
        self,
        *,
        node: WorkflowNode,
        workflow_input: Dict[str, Any],
        workflow_context: Dict[str, Any],
        step_outputs: Dict[str, Any],
    ) -> Dict[str, Any]:
        ...


class DeterministicWorkflowCapabilityExecutor:
    """
    Deterministic capability executor for Phase18 workflow runtime.

    Supported behavior:
    - normal success path
    - deterministic failure injection via workflow input or node metadata

    Failure injection rules:
    1. workflow_input["force_fail_node_id"] == node.node_id
    2. node.metadata["force_fail"] is True

    This keeps failure-path testing deterministic without requiring live model/runtime calls.
    """

    async def execute(
        self,
        *,
        node: WorkflowNode,
        workflow_input: Dict[str, Any],
        workflow_context: Dict[str, Any],
        step_outputs: Dict[str, Any],
    ) -> Dict[str, Any]:
        if node.capability_ref is None:
            raise WorkflowCapabilityExecutorError(
                f"Capability node missing capability_ref: {node.node_id}"
            )

        if workflow_input.get("force_fail_node_id") == node.node_id:
            raise WorkflowCapabilityExecutionFailed(
                f"Deterministic capability failure injected for node: {node.node_id}"
            )

        if bool(node.metadata.get("force_fail", False)):
            raise WorkflowCapabilityExecutionFailed(
                f"Deterministic node metadata failure injected for node: {node.node_id}"
            )

        step_outputs_snapshot = deepcopy(step_outputs)

        return {
            "node_id": node.node_id,
            "node_name": node.name,
            "capability": node.capability_ref.model_dump(mode="json"),
            "status": "succeeded",
            "workflow_input": deepcopy(workflow_input),
            "workflow_context": deepcopy(workflow_context),
            "previous_step_outputs": step_outputs_snapshot,
            "message": f"deterministic capability executed: {node.node_id}",
        }