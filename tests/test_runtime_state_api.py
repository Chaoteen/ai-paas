from fastapi.testclient import TestClient

from main import app


def test_runtime_info_exposes_state_components():
    with TestClient(app) as client:
        resp = client.get("/runtime/info")
        assert resp.status_code == 200
        data = resp.json()

        assert data["ok"] is True
        assert data["has_agent_runtime"] is True
        assert data["has_state_store"] is True
        assert data["has_idempotency_store"] is True


def test_task_state_404_when_missing():
    with TestClient(app) as client:
        resp = client.get("/runtime/tasks/nonexistent-task/state")
        assert resp.status_code == 404
        assert resp.json()["detail"] == "task_state_not_found"