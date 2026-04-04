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
    - deterministic fail-N-times for retry testing

    Failure injection rules (checked in this order):
    1. workflow_input["fail_n_times_by_node_id"][node.node_id] > current_attempt_failures
    2. workflow_input["force_fail_node_id"] == node.node_id
    3. node.metadata["fail_n_times"] > current_attempt_failures
    4. node.metadata["force_fail"] is True
    """

    def _get_fail_n_times(self, *, node: WorkflowNode, workflow_input: Dict[str, Any]) -> int:
        value = 0

        mapping = workflow_input.get("fail_n_times_by_node_id", {})
        if isinstance(mapping, dict):
            candidate = mapping.get(node.node_id, 0)
            if isinstance(candidate, int) and candidate > 0:
                value = max(value, candidate)

        metadata_candidate = node.metadata.get("fail_n_times", 0)
        if isinstance(metadata_candidate, int) and metadata_candidate > 0:
            value = max(value, metadata_candidate)

        return value

    def _get_current_failure_count(
        self,
        *,
        node: WorkflowNode,
        step_outputs: Dict[str, Any],
    ) -> int:
        retry_state = step_outputs.get("__retry_state__", {})
        if not isinstance(retry_state, dict):
            return 0

        node_state = retry_state.get(node.node_id, {})
        if not isinstance(node_state, dict):
            return 0

        failure_count = node_state.get("failure_count", 0)
        if isinstance(failure_count, int) and failure_count >= 0:
            return failure_count
        return 0

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

        fail_n_times = self._get_fail_n_times(node=node, workflow_input=workflow_input)
        current_failure_count = self._get_current_failure_count(
            node=node,
            step_outputs=step_outputs,
        )
        if current_failure_count < fail_n_times:
            raise WorkflowCapabilityExecutionFailed(
                f"Deterministic capability fail_n_times injected for node: {node.node_id}; "
                f"failure_count={current_failure_count + 1}/{fail_n_times}"
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