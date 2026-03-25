from fastapi import FastAPI
from fastapi.testclient import TestClient

from gateway.api.workflow_definitions import (
    get_workflow_session_factory,
    router,
)


class DummySession:
    async def commit(self):
        return None

    async def rollback(self):
        return None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class FakeWorkflowDefinition:
    def __init__(self, data):
        self.workflow_key = data["workflow_key"]
        self.workflow_version = data["workflow_version"]
        self.display_name = data["display_name"]
        self.status = type("Status", (), {"value": data["status"]})()
        self.input_schema = data.get("input_schema", {})
        self.output_schema = data.get("output_schema", {})
        self.nodes = data.get("nodes", [])
        self.edges = data.get("edges", [])
        self.policies = data.get("policies", {})
        self.governance = data.get("governance", {})
        self.metadata = data.get("metadata", {})
        self.checksum = data.get("checksum")
        self.created_by = data.get("created_by")
        self.updated_by = data.get("updated_by")
        import datetime
        now = datetime.datetime.now(datetime.timezone.utc)
        self.created_at = now
        self.updated_at = now

    def model_dump(self, mode="json"):
        return {
            "workflow_key": self.workflow_key,
            "workflow_version": self.workflow_version,
            "display_name": self.display_name,
            "status": self.status.value,
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
            "nodes": self.nodes,
            "edges": self.edges,
            "policies": self.policies,
            "governance": self.governance,
            "metadata": self.metadata,
            "checksum": self.checksum,
            "created_by": self.created_by,
            "updated_by": self.updated_by,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class FakeWorkflowDefinitionRepository:
    store = {}

    def __init__(self, session):
        self.session = session

    async def create(self, definition):
        key = (definition.workflow_key, definition.workflow_version)
        self.__class__.store[key] = definition
        return definition

    async def get(self, *, workflow_key: str, workflow_version: str):
        return self.__class__.store.get((workflow_key, workflow_version))

    async def get_active(self, *, workflow_key: str):
        for (key, _version), definition in self.__class__.store.items():
            if key == workflow_key and definition.status.value == "active":
                return definition
        return None


def _build_app():
    import gateway.api.workflow_definitions as module

    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    async def override_session_factory():
        def _factory():
            return DummySession()
        return _factory

    app.dependency_overrides[get_workflow_session_factory] = override_session_factory
    module.WorkflowDefinitionRepository = FakeWorkflowDefinitionRepository
    return app


def test_create_and_get_workflow_definition_api():
    FakeWorkflowDefinitionRepository.store = {}

    app = _build_app()
    client = TestClient(app)

    create_resp = client.post(
        "/api/v1/workflow/definitions",
        json={
            "workflow_key": "pricing.quote.flow",
            "workflow_version": "1.0.0",
            "display_name": "Pricing Quote Flow",
            "status": "active",
            "input_schema": {"type": "object"},
            "output_schema": {"type": "object"},
            "nodes": [
                {"node_id": "start", "node_type": "start", "name": "Start"},
                {
                    "node_id": "draft_quote",
                    "node_type": "capability",
                    "name": "Draft Quote",
                    "capability_ref": {
                        "kind": "agent",
                        "key": "sales.quote.drafter",
                        "version": "1.2.0",
                    },
                },
                {"node_id": "end", "node_type": "end", "name": "End"},
            ],
            "edges": [
                {
                    "edge_id": "e1",
                    "source_node_id": "start",
                    "target_node_id": "draft_quote",
                },
                {
                    "edge_id": "e2",
                    "source_node_id": "draft_quote",
                    "target_node_id": "end",
                },
            ],
            "policies": {"retry": "node-level"},
            "governance": {"tenant_scoped": True},
            "metadata": {"owner": "workflow-team"},
        },
    )
    assert create_resp.status_code == 201
    create_body = create_resp.json()
    assert create_body["workflow_key"] == "pricing.quote.flow"
    assert create_body["workflow_version"] == "1.0.0"
    assert create_body["status"] == "active"

    get_resp = client.get("/api/v1/workflow/definitions/pricing.quote.flow/1.0.0")
    assert get_resp.status_code == 200
    get_body = get_resp.json()
    assert get_body["workflow_key"] == "pricing.quote.flow"
    assert get_body["workflow_version"] == "1.0.0"
    assert get_body["display_name"] == "Pricing Quote Flow"

    active_resp = client.get("/api/v1/workflow/definitions/pricing.quote.flow/active")
    assert active_resp.status_code == 200
    active_body = active_resp.json()
    assert active_body["workflow_key"] == "pricing.quote.flow"
    assert active_body["workflow_version"] == "1.0.0"