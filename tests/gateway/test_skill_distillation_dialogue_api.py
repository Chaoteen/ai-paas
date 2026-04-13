from __future__ import annotations

from fastapi.testclient import TestClient

from gateway.main import app


def _headers(tenant_id: str = "tenant-dialogue", user_id: str = "alice") -> dict[str, str]:
    return {
        "X-Tenant-Id": tenant_id,
        "X-User-Id": user_id,
        "X-Display-Name": user_id,
        "X-Is-Admin": "true",
    }


def test_distill_from_dialogue_creates_session_and_draft() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/skill-drafts/distill-from-dialogue",
            headers=_headers(),
            json={
                "session_title": "报价邮件技能蒸馏",
                "draft_name": "报价邮件助手",
                "intent_summary": "把用户描述蒸馏成报价回复技能",
                "dialogue_turns": [
                    {"speaker": "user", "text": "先读取客户邮件"},
                    {"speaker": "assistant", "text": "再判断是不是有效询盘"},
                    {"speaker": "user", "text": "最后生成标准报价回复"},
                ],
            },
        )
        assert response.status_code == 201, response.text

        body = response.json()
        assert body["dialogue_turn_count"] == 3
        assert body["recording_session"]["source_type"] == "dialogue"
        assert body["recording_session"]["status"] == "distilled"
        assert body["skill_draft"]["distillation_source_type"] == "dialogue"
        assert body["skill_draft"]["draft_version"] == "v1"
        assert body["recording_session"]["latest_skill_draft_id"] == body["skill_draft"]["skill_draft_id"]


def test_distill_from_dialogue_reuses_existing_session() -> None:
    with TestClient(app) as client:
        create_session = client.post(
            "/api/v1/recording/sessions",
            headers=_headers(),
            json={
                "source_type": "dialogue",
                "title": "已有会话",
                "description": None,
                "context_json": {},
                "source_metadata_json": {},
            },
        )
        assert create_session.status_code == 201, create_session.text
        session_id = create_session.json()["recording_session_id"]

        response = client.post(
            "/api/v1/skill-drafts/distill-from-dialogue",
            headers=_headers(),
            json={
                "recording_session_id": session_id,
                "session_title": "已有会话",
                "draft_name": "复用会话技能",
                "dialogue_turns": [
                    {"speaker": "user", "text": "第一步"},
                    {"speaker": "user", "text": "第二步"},
                ],
            },
        )
        assert response.status_code == 201, response.text
        body = response.json()
        assert body["recording_session"]["recording_session_id"] == session_id
        assert body["recording_session"]["status"] == "distilled"


def test_distill_from_dialogue_rejects_empty_turns() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/skill-drafts/distill-from-dialogue",
            headers=_headers(),
            json={
                "session_title": "空对话",
                "draft_name": "空对话技能",
                "dialogue_turns": [],
            },
        )
        assert response.status_code == 400
        assert "dialogue_turns" in response.json()["detail"]