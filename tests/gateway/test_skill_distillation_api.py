from __future__ import annotations

from fastapi.testclient import TestClient

from gateway.main import app


def _headers(tenant_id: str = "tenant-a", user_id: str = "alice") -> dict[str, str]:
    return {
        "X-Tenant-Id": tenant_id,
        "X-User-Id": user_id,
        "X-Display-Name": user_id,
        "X-Is-Admin": "true",
    }


def _create_session(client: TestClient, tenant_id: str = "tenant-a", user_id: str = "alice") -> str:
    response = client.post(
        "/api/v1/recording/sessions",
        headers=_headers(tenant_id, user_id),
        json={
            "source_type": "dialogue",
            "distillation_mode": "dialogue_only",
            "title": "报价技能蒸馏",
            "description": "从对话蒸馏报价动作",
            "context_json": {"department": "sales"},
            "source_metadata_json": {"entry": "manual"},
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["recording_session_id"]


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
        "steps": [
            {"node_id": "read_mail", "node_type": "capability"},
            {"node_id": "classify", "node_type": "capability"},
            {"node_id": "draft_reply", "node_type": "capability"},
        ],
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


def test_recording_session_event_draft_flow() -> None:
    with TestClient(app) as client:
        session_id = _create_session(client)

        event_response = client.post(
            f"/api/v1/recording/sessions/{session_id}/events",
            headers=_headers(),
            json={
                "idempotency_key": "evt-1",
                "event_type": "dialogue_step",
                "actor_type": "user",
                "payload_json": {"text": "先读取客户询价邮件，再判断是否垃圾询盘"},
                "source_ref_json": {},
                "metadata_json": {},
            },
        )
        assert event_response.status_code == 201, event_response.text
        assert event_response.json()["sequence_no"] == 1

        duplicate_response = client.post(
            f"/api/v1/recording/sessions/{session_id}/events",
            headers=_headers(),
            json={
                "idempotency_key": "evt-1",
                "event_type": "dialogue_step",
                "actor_type": "user",
                "payload_json": {"text": "重复提交"},
                "source_ref_json": {},
                "metadata_json": {},
            },
        )
        assert duplicate_response.status_code == 201, duplicate_response.text
        assert duplicate_response.json()["sequence_no"] == 1

        draft_response = client.post(
            "/api/v1/skill-drafts",
            headers=_headers(),
            json={
                "recording_session_id": session_id,
                "previous_skill_draft_id": None,
                "draft_key": "quote_email_skill",
                "name": "邮件报价助手",
                "intent_summary": "从询价邮件生成标准报价草稿",
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
        assert draft_response.status_code == 201, draft_response.text
        draft_body = draft_response.json()
        assert draft_body["draft_version"] == "v1"

        session_detail = client.get(
            f"/api/v1/recording/sessions/{session_id}",
            headers=_headers(),
        )
        assert session_detail.status_code == 200
        assert session_detail.json()["latest_skill_draft_id"] == draft_body["skill_draft_id"]


def test_skill_draft_state_actions() -> None:
    with TestClient(app) as client:
        draft_response = client.post(
            "/api/v1/skill-drafts",
            headers=_headers(),
            json={
                "recording_session_id": None,
                "previous_skill_draft_id": None,
                "draft_key": "expense_reimbursement_skill",
                "name": "报销单归集助手",
                "intent_summary": "收集发票、识别申请单、写回财务系统",
                "distillation_source_type": "imported",
                "input_schema_json": _io_schema(),
                "output_schema_json": _io_schema(),
                "draft_definition_json": {
                    "draft_type": "task_skill",
                    "steps": [],
                    "inputs": [],
                    "outputs": [],
                    "guardrails": {},
                    "hints": {},
                },
                "distillation_notes_json": {},
                "execution_binding_json": _default_binding(),
                "derived_from_json": _derived_from(None, "imported"),
                "metadata_json": {},
            },
        )
        assert draft_response.status_code == 201, draft_response.text
        skill_draft_id = draft_response.json()["skill_draft_id"]

        submit_review = client.post(
            f"/api/v1/skill-drafts/{skill_draft_id}/submit-review",
            headers=_headers(),
        )
        assert submit_review.status_code == 200, submit_review.text
        assert submit_review.json()["status"] == "reviewing"

        accept = client.post(
            f"/api/v1/skill-drafts/{skill_draft_id}/accept",
            headers=_headers(),
        )
        assert accept.status_code == 200, accept.text
        assert accept.json()["status"] == "accepted"

        invalid = client.post(
            f"/api/v1/skill-drafts/{skill_draft_id}/reject",
            headers=_headers(),
        )
        assert invalid.status_code == 409


def test_patch_forbidden_fields_rejected() -> None:
    with TestClient(app) as client:
        session_id = _create_session(client)
        response = client.patch(
            f"/api/v1/recording/sessions/{session_id}",
            headers=_headers(),
            json={"status": "distilled"},
        )
        assert response.status_code == 400
        assert "forbidden" in response.json()["detail"].lower()