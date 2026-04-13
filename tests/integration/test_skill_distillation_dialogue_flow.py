from __future__ import annotations

from fastapi.testclient import TestClient

from gateway.main import app


def _headers(tenant_id: str = "tenant-dialogue-int", user_id: str = "integration-user") -> dict[str, str]:
    return {
        "X-Tenant-Id": tenant_id,
        "X-User-Id": user_id,
        "X-Display-Name": user_id,
        "X-Is-Admin": "true",
    }


def test_dialogue_distillation_minimal_flow() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/skill-drafts/distill-from-dialogue",
            headers=_headers(),
            json={
                "session_title": "报销技能蒸馏",
                "draft_name": "报销归集助手",
                "draft_key": "expense_dialogue_skill_int",
                "intent_summary": "把报销处理步骤蒸馏成草稿技能",
                "dialogue_turns": [
                    {"speaker": "user", "text": "先读取员工上传的票据"},
                    {"speaker": "assistant", "text": "再匹配申请单和费用类型"},
                    {"speaker": "user", "text": "最后输出可写入财务系统的数据"},
                ],
            },
        )
        assert response.status_code == 201, response.text
        body = response.json()

        session_id = body["recording_session"]["recording_session_id"]
        draft_id = body["skill_draft"]["skill_draft_id"]

        assert body["recording_session"]["status"] == "distilled"
        assert body["skill_draft"]["recording_session_id"] == session_id
        assert body["recording_session"]["latest_skill_draft_id"] == draft_id
        assert body["skill_draft"]["derived_from_json"]["source_event_range"]["from_sequence_no"] == 1
        assert body["skill_draft"]["derived_from_json"]["source_event_range"]["to_sequence_no"] == 3