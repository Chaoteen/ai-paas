from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from gateway.main import app


pytestmark = pytest.mark.integration


def _require_database() -> None:
    if not os.getenv("DATABASE_URL"):
        pytest.skip("DATABASE_URL is not set")


def _headers(tenant_id: str = "tenant-pg-dialogue", user_id: str = "integration-user") -> dict[str, str]:
    return {
        "X-Tenant-Id": tenant_id,
        "X-User-Id": user_id,
        "X-Display-Name": user_id,
        "X-Is-Admin": "true",
    }


def test_postgres_dialogue_distillation_flow_end_to_end() -> None:
    _require_database()

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/skill-drafts/distill-from-dialogue",
            headers=_headers(),
            json={
                "session_title": "PG 报价技能蒸馏",
                "draft_name": "PG 报价助手",
                "draft_key": "quote_dialogue_pg_skill",
                "intent_summary": "在真实 Postgres 下验证 dialogue distillation",
                "dialogue_turns": [
                    {"speaker": "user", "text": "第一步读取客户询盘"},
                    {"speaker": "assistant", "text": "第二步判断是否有效询盘"},
                    {"speaker": "user", "text": "第三步生成标准报价草稿"},
                ],
            },
        )
        assert response.status_code == 201, response.text

        body = response.json()
        session = body["recording_session"]
        draft = body["skill_draft"]

        assert body["dialogue_turn_count"] == 3
        assert session["status"] == "distilled"
        assert session["source_type"] == "dialogue"
        assert draft["recording_session_id"] == session["recording_session_id"]
        assert session["latest_skill_draft_id"] == draft["skill_draft_id"]
        assert draft["derived_from_json"]["source_event_range"]["from_sequence_no"] == 1
        assert draft["derived_from_json"]["source_event_range"]["to_sequence_no"] == 3

        session_detail = client.get(
            f"/api/v1/recording/sessions/{session['recording_session_id']}",
            headers=_headers(),
        )
        assert session_detail.status_code == 200
        assert session_detail.json()["latest_skill_draft_id"] == draft["skill_draft_id"]