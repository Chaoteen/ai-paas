from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from gateway.api.workflow_executions import (
    get_workflow_execution_session_factory,
    router,
)
from runtime.workflows.models import WorkflowExecutionStatus


class DummySession:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class FakeExecution:
    def __init__(self):
        now = datetime.now(timezone.utc)
        self.workflow_execution_id = "wf-exec-001"
        self.task_id = "task-001"
        self.tenant_id = "dev"
        self.workflow_key = "pricing.quote.flow"
        self.workflow_version = "1.0.0"
        self.status = WorkflowExecutionStatus.RUNNING
        self.definition_snapshot_json = {
            "workflow_key": "pricing.quote.flow",
            "workflow_version": "1.0.0",
        }
        self.input_json = {"customer_name": "Acme"}
        self.context_json = {"channel": "api"}
        self.system_context_json = {"task_id": "task-001"}
        self.output_json = None
        self.error_text = None
        self.active_node_ids = ["draft_quote"]
        self.resolved_capabilities_json = {"draft_quote": {"kind": "agent"}}
        self.governance_json = {"tenant_scoped": True}
        self.trace_json = {"trace_id": "trace-001"}
        self.created_at = now
        self.started_at = None
        self.finished_at = None
        self.updated_at = now


class FakeWorkflowExecutionRepository:
    def __init__(self, session):
        self.session = session

    async def get(self, workflow_execution_id: str):
        if workflow_execution_id == "wf-exec-001":
            return FakeExecution()
        return None

    async def get_by_task_id(self, task_id: str):
        if task_id == "task-001":
            return FakeExecution()
        return None


def _build_app():
    import gateway.api.workflow_executions as module

    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    async def override_session_factory():
        def _factory():
            return DummySession()
        return _factory

    app.dependency_overrides[
        get_workflow_execution_session_factory
    ] = override_session_factory
    module.WorkflowExecutionRepository = FakeWorkflowExecutionRepository
    return app


def test_get_workflow_execution_api():
    app = _build_app()
    client = TestClient(app)

    by_task_resp = client.get("/api/v1/workflow/executions/by-task/task-001")
    assert by_task_resp.status_code == 200
    by_task_body = by_task_resp.json()
    assert by_task_body["task_id"] == "task-001"
    assert by_task_body["workflow_execution_id"] == "wf-exec-001"
    assert by_task_body["status"] == "running"
    assert by_task_body["active_node_ids"] == ["draft_quote"]

    by_exec_resp = client.get("/api/v1/workflow/executions/wf-exec-001")
    assert by_exec_resp.status_code == 200
    by_exec_body = by_exec_resp.json()
    assert by_exec_body["workflow_execution_id"] == "wf-exec-001"
    assert by_exec_body["workflow_key"] == "pricing.quote.flow"
    assert by_exec_body["workflow_version"] == "1.0.0"