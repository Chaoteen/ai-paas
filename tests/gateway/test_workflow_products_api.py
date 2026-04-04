from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient

from gateway.main import app


def _product_payload() -> dict:
    return {
        "product": {
            "product_key": "solar_lamp_product_plan",
            "product_version": "1.0.0",
            "display_name": "太阳能庭院灯产品规划助手",
            "status": "active",
            "public_api_schema_json": {
                "type": "object",
                "properties": {
                    "target_market": {"type": "string"},
                    "cost_target": {"type": "number"},
                    "style_direction": {"type": "string"},
                },
                "required": ["target_market", "cost_target"],
            },
            "ui_schema_json": {
                "form": [
                    {"field": "target_market", "component": "input"},
                    {"field": "cost_target", "component": "number"},
                    {"field": "style_direction", "component": "textarea"},
                ]
            },
            "execution_binding": {
                "workflow_key": "solar_lamp_internal_flow",
                "workflow_version": "3.2.0",
                "default_input_json": {},
                "default_context_json": {"channel": "product_api"},
                "input_mapping_json": {},
            },
            "governance_json": {},
            "metadata_json": {"category": "manufacturing"},
            "visibility": "tenant",
        }
    }


def _submit_payload() -> dict:
    unique = uuid4().hex
    return {
        "tenant_id": "dev",
        "product_key": "solar_lamp_product_plan",
        "input_json": {
            "target_market": "EU garden retail",
            "cost_target": 12.5,
            "style_direction": "warm ambient minimalism",
        },
        "context_json": {"operator": "pm_assistant"},
        "metadata_json": {"request_channel": "web"},
        "trigger_source": "workflow_product_api",
        "idempotency_key": f"order-{unique}",
        "correlation_id": f"corr-{unique}",
    }


def test_create_workflow_product() -> None:
    with TestClient(app) as client:
        response = client.post("/api/v1/workflow/products", json=_product_payload())
        assert response.status_code == 201, response.text

        body = response.json()
        assert body["product"]["product_key"] == "solar_lamp_product_plan"
        assert body["product"]["product_version"] == "1.0.0"
        assert body["product"]["execution_binding"]["workflow_key"] == "solar_lamp_internal_flow"
        assert body["product"]["execution_binding"]["workflow_version"] == "3.2.0"


def test_submit_workflow_product() -> None:
    with TestClient(app) as client:
        create_resp = client.post("/api/v1/workflow/products", json=_product_payload())
        assert create_resp.status_code == 201, create_resp.text

        submit_resp = client.post("/api/v1/workflow/products/submit", json=_submit_payload())
        assert submit_resp.status_code == 202, submit_resp.text

        body = submit_resp.json()
        assert body["task_type"] == "workflow"
        assert body["queue_name"] == "workflow_tasks"
        assert body["stream_name"] == "workflow_tasks"
        assert body["status"] == "queued"
        assert body["durable"] is True
        assert body["bound_workflow_key"] == "solar_lamp_internal_flow"
        assert body["bound_workflow_version"] == "3.2.0"


def test_submit_workflow_product_not_found() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/workflow/products/submit",
            json={
                "tenant_id": "dev",
                "product_key": "missing_product",
                "input_json": {},
                "context_json": {},
                "metadata_json": {},
            },
        )
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()