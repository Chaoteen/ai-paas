from __future__ import annotations

from fastapi.testclient import TestClient

from gateway.main import app


def test_request_context_enforces_tenant_isolation() -> None:
    with TestClient(app) as client:
        create_resp = client.post(
            "/api/v1/recording/sessions",
            headers={
                "X-Tenant-Id": "tenant-a",
                "X-User-Id": "alice",
                "X-Display-Name": "alice",
                "X-Is-Admin": "true",
            },
            json={
                "source_type": "dialogue",
                "title": "tenant-a 会话",
                "description": None,
                "context_json": {},
                "source_metadata_json": {},
            },
        )
        assert create_resp.status_code == 201, create_resp.text
        session_id = create_resp.json()["recording_session_id"]

        forbidden_resp = client.get(
            f"/api/v1/recording/sessions/{session_id}",
            headers={
                "X-Tenant-Id": "tenant-b",
                "X-User-Id": "bob",
                "X-Display-Name": "bob",
                "X-Is-Admin": "true",
            },
        )
        assert forbidden_resp.status_code == 404

        owner_resp = client.get(
            f"/api/v1/recording/sessions/{session_id}",
            headers={
                "X-Tenant-Id": "tenant-a",
                "X-User-Id": "alice",
                "X-Display-Name": "alice",
                "X-Is-Admin": "true",
            },
        )
        assert owner_resp.status_code == 200


def test_request_context_defaults_to_dev_when_headers_missing() -> None:
    with TestClient(app) as client:
        create_resp = client.post(
            "/api/v1/recording/sessions",
            json={
                "source_type": "dialogue",
                "title": "默认 dev 上下文",
                "description": None,
                "context_json": {},
                "source_metadata_json": {},
            },
        )
        assert create_resp.status_code == 201, create_resp.text
        body = create_resp.json()
        assert body["tenant_id"] == "dev"
        assert body["created_by"] == "dev"