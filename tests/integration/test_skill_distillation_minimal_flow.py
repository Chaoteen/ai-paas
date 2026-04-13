from __future__ import annotations

from fastapi.testclient import TestClient

from gateway.main import app


def _headers(tenant_id: str = "tenant-int", user_id: str = "integration-user") -> dict[str, str]:
    return {
        "X-Tenant-Id": tenant_id,
        "X-User-Id": user_id,
        "X-Display-Name": user_id,
        "X-Is-Admin": "true",
    }


def _default_binding() -> dict:
    return {
        "binding_type": "unbound",
        "target_ref": {"object_type": None, "object_id": None},
        "config_json": {},
    }


def _io_schema() -> dict:
    return {
        "type": "object",
        "properties": {},
        "required": [],
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


def _derived_from(session_id: str | None, source_kind: str) -> dict:
    return {
        "recording_session_id": session_id,
        "source_event_range": {
            "from_sequence_no": None,
            "to_sequence_no": None,
        },
        "source_kind": source_kind,
    }


def test_session_multi_draft_latest_pointer_updates() -> None:
    with TestClient(app) as client:
        session_resp = client.post(
            "/api/v1/recording/sessions",
            headers=_headers(),
            json={
                "source_type": "dialogue",
                "distillation_mode": "dialogue_only",
                "title": "多版本报价蒸馏",
                "description": "测试 latest pointer",
                "context_json": {},
                "source_metadata_json": {},
            },
        )
        assert session_resp.status_code == 201, session_resp.text
        session_id = session_resp.json()["recording_session_id"]

        first = client.post(
            "/api/v1/skill-drafts",
            headers=_headers(),
            json={
                "recording_session_id": session_id,
                "previous_skill_draft_id": None,
                "draft_key": "quote_skill",
                "name": "报价助手",
                "intent_summary": "v1",
                "distillation_source_type": "dialogue",
                "input_schema_json": _io_schema(),
                "output_schema_json": _io_schema(),
                "draft_definition_json": _draft_definition(),
                "distillation_notes_json": {},
                "execution_binding_json": _default_binding(),
                "derived_from_json": _derived_from(session_id, "dialogue"),
                "metadata_json": {},
            },
        )
        assert first.status_code == 201, first.text
        first_id = first.json()["skill_draft_id"]
        assert first.json()["draft_version"] == "v1"

        second = client.post(
            "/api/v1/skill-drafts",
            headers=_headers(),
            json={
                "recording_session_id": session_id,
                "previous_skill_draft_id": first_id,
                "draft_key": "quote_skill",
                "name": "报价助手",
                "intent_summary": "v2",
                "distillation_source_type": "dialogue",
                "input_schema_json": _io_schema(),
                "output_schema_json": _io_schema(),
                "draft_definition_json": _draft_definition(),
                "distillation_notes_json": {},
                "execution_binding_json": _default_binding(),
                "derived_from_json": _derived_from(session_id, "dialogue"),
                "metadata_json": {},
            },
        )
        assert second.status_code == 201, second.text
        second_id = second.json()["skill_draft_id"]
        assert second.json()["draft_version"] == "v2"
        assert first_id != second_id

        detail = client.get(
            f"/api/v1/recording/sessions/{session_id}",
            headers=_headers(),
        )
        assert detail.status_code == 200
        assert detail.json()["latest_skill_draft_id"] == second_id


def test_invalid_session_transition_rejected() -> None:
    with TestClient(app) as client:
        session_resp = client.post(
            "/api/v1/recording/sessions",
            headers=_headers("tenant-int-2"),
            json={
                "source_type": "dialogue",
                "distillation_mode": "dialogue_only",
                "title": "状态机测试",
                "description": None,
                "context_json": {},
                "source_metadata_json": {},
            },
        )
        assert session_resp.status_code == 201, session_resp.text
        session_id = session_resp.json()["recording_session_id"]

        invalid = client.post(
            f"/api/v1/recording/sessions/{session_id}/mark-distilled",
            headers=_headers("tenant-int-2"),
        )
        assert invalid.status_code == 409