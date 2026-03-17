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


def test_submit_task_is_idempotent():
    with TestClient(app) as client:
        payload = {
            "tenant_id": "tenant-test",
            "task_id": "task-idem-001",
            "workflow_id": "wf-idem-001",
            "correlation_id": "corr-idem-001",
            "required_capability": "echo",
            "input": {"text": "hello"},
            "metadata": {"source": "test"},
        }

        first = client.post("/runtime/tasks/submit", json=payload)
        assert first.status_code == 200
        first_data = first.json()
        assert first_data["ok"] is True
        assert first_data["deduplicated"] is False
        assert first_data["event"] is not None

        second = client.post("/runtime/tasks/submit", json=payload)
        assert second.status_code == 200
        second_data = second.json()
        assert second_data["ok"] is True
        assert second_data["deduplicated"] is True
        assert second_data["event"] is None
        assert second_data["task_state"]["task_id"] == "task-idem-001"