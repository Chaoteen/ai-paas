from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from gateway.main import app


pytestmark = pytest.mark.integration


def _headers(tenant_id: str = "tenant-int", user_id: str = "integration-user") -> dict[str, str]:
    return {
        "X-Tenant-Id": tenant_id,
        "X-User-Id": user_id,
        "X-Display-Name": user_id,
        "X-Is-Admin": "true",
    }


def _binding() -> dict:
    return {
        "binding_type": "unbound",
        "target_ref": {"object_type": None, "object_id": None},
        "config_json": {},
    }


def _draft_definition() -> dict:
    return {
        "draft_type": "task_skill",
        "steps": [],
        "inputs": [],
        "outputs": [],
        "guardrails": {},
        "hints": {},
    }


def _derived_from(session_id: str | None = None, source_kind: str = "imported") -> dict:
    return {
        "recording_session_id": session_id,
        "source_event_range": {
            "from_sequence_no": None,
            "to_sequence_no": None,
        },
        "source_kind": source_kind,
    }


@pytest.fixture(scope="module", autouse=True)
def require_database_url() -> None:
    database_url = os.getenv("DATABASE_URL", "")
    if not database_url:
        pytest.skip("DATABASE_URL is not set; skip postgres integration test")


def test_postgres_phase1_session_event_draft_flow() -> None:
    with TestClient(app) as client:
        session_resp = client.post(
            "/api/v1/recording/sessions",
            headers=_headers(),
            json={
                "source_type": "dialogue",
                "distillation_mode": "dialogue_only",
                "title": "Postgres 蒸馏集成测试",
                "description": "验证真实 DB 下的 phase1 主线",
                "context_json": {"channel": "integration"},
                "source_metadata_json": {"source": "pytest"},
            },
        )
        assert session_resp.status_code == 201, session_resp.text
        session_id = session_resp.json()["recording_session_id"]

        event_1 = client.post(
            f"/api/v1/recording/sessions/{session_id}/events",
            headers=_headers(),
            json={
                "idempotency_key": "pg-evt-1",
                "event_type": "dialogue_step",
                "actor_type": "user",
                "payload_json": {"text": "第一步读取询价需求"},
                "source_ref_json": {},
                "metadata_json": {},
            },
        )
        assert event_1.status_code == 201, event_1.text
        assert event_1.json()["sequence_no"] == 1

        event_2 = client.post(
            f"/api/v1/recording/sessions/{session_id}/events",
            headers=_headers(),
            json={
                "idempotency_key": "pg-evt-2",
                "event_type": "system_inference",
                "actor_type": "system",
                "payload_json": {"summary": "识别为报价类技能"},
                "source_ref_json": {},
                "metadata_json": {},
            },
        )
        assert event_2.status_code == 201, event_2.text
        assert event_2.json()["sequence_no"] == 2

        draft_v1 = client.post(
            "/api/v1/skill-drafts",
            headers=_headers(),
            json={
                "recording_session_id": session_id,
                "previous_skill_draft_id": None,
                "draft_key": "quote_skill_pg",
                "name": "报价助手PG",
                "intent_summary": "v1 版本",
                "distillation_source_type": "dialogue",
                "input_schema_json": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
                "output_schema_json": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
                "draft_definition_json": _draft_definition(),
                "distillation_notes_json": {},
                "execution_binding_json": _binding(),
                "derived_from_json": _derived_from(session_id, "dialogue"),
                "metadata_json": {},
            },
        )
        assert draft_v1.status_code == 201, draft_v1.text
        assert draft_v1.json()["draft_version"] == "v1"
        draft_v1_id = draft_v1.json()["skill_draft_id"]

        draft_v2 = client.post(
            "/api/v1/skill-drafts",
            headers=_headers(),
            json={
                "recording_session_id": session_id,
                "previous_skill_draft_id": draft_v1_id,
                "draft_key": "quote_skill_pg",
                "name": "报价助手PG",
                "intent_summary": "v2 版本",
                "distillation_source_type": "dialogue",
                "input_schema_json": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
                "output_schema_json": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
                "draft_definition_json": _draft_definition(),
                "distillation_notes_json": {},
                "execution_binding_json": _binding(),
                "derived_from_json": _derived_from(session_id, "dialogue"),
                "metadata_json": {},
            },
        )
        assert draft_v2.status_code == 201, draft_v2.text
        assert draft_v2.json()["draft_version"] == "v2"

        detail_resp = client.get(
            f"/api/v1/recording/sessions/{session_id}",
            headers=_headers(),
        )
        assert detail_resp.status_code == 200
        assert detail_resp.json()["latest_skill_draft_id"] == draft_v2.json()["skill_draft_id"]


def test_postgres_phase1_illegal_transition() -> None:
    with TestClient(app) as client:
        session_resp = client.post(
            "/api/v1/recording/sessions",
            headers=_headers(),
            json={
                "source_type": "dialogue",
                "distillation_mode": "dialogue_only",
                "title": "非法状态迁移测试",
                "description": None,
                "context_json": {},
                "source_metadata_json": {},
            },
        )
        assert session_resp.status_code == 201, session_resp.text
        session_id = session_resp.json()["recording_session_id"]

        invalid_resp = client.post(
            f"/api/v1/recording/sessions/{session_id}/mark-distilled",
            headers=_headers(),
        )
        assert invalid_resp.status_code == 409