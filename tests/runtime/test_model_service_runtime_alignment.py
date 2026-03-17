from __future__ import annotations

from runtime.model_service import ModelInvocationContext
from runtime.execution_context import ExecutionContext


def test_model_invocation_context_aligns_with_execution_context() -> None:
    execution_context = ExecutionContext(
        task_id="task-1",
        tenant_id="tenant-1",
        workflow_id="wf-1",
        correlation_id="corr-1",
        user_id="user-1",
        selected_agent_id="agent-1",
        required_capability="chat",
        workspace_root="/tmp/workspace",
        trace_id="trace-1",
        requested_capabilities=["chat"],
        allowed_capabilities=["chat"],
        secrets_scope={},
        metadata={"k": "v"},
        input_payload={"text": "hello"},
    )

    invocation_context = ModelInvocationContext.from_execution_context(
        execution_context,
        model_ref="default",
    )

    assert invocation_context.task_id == "task-1"
    assert invocation_context.tenant_id == "tenant-1"
    assert invocation_context.workflow_id == "wf-1"
    assert invocation_context.correlation_id == "corr-1"
    assert invocation_context.user_id == "user-1"
    assert invocation_context.model_ref == "default"
    assert invocation_context.metadata == {"k": "v"}