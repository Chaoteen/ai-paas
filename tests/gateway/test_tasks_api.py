from fastapi.testclient import TestClient

from gateway.main import app
import runtime.queue.task_store as task_store_module


client = TestClient(app)


def test_submit_agent_task_and_fetch():
    task_store_module._task_store = task_store_module.InMemoryTaskStore()

    submit_resp = client.post(
        "/api/v1/agent/submit",
        json={
            "agent_id": "echo",
            "input": "hello queue",
            "tenant_id": "tenant-a",
            "priority": "high",
        },
    )

    assert submit_resp.status_code == 200
    submit_body = submit_resp.json()

    assert submit_body["success"] is True
    assert submit_body["task_type"] == "agent"
    assert submit_body["status"] == "queued"
    assert submit_body["queue_name"] == "agent"
    assert submit_body["priority"] == "high"

    task_id = submit_body["task_id"]

    fetch_resp = client.get(f"/api/v1/tasks/{task_id}")
    assert fetch_resp.status_code == 200

    fetch_body = fetch_resp.json()
    assert fetch_body["success"] is True
    assert fetch_body["task"]["task_id"] == task_id
    assert fetch_body["task"]["task_type"] == "agent"
    assert fetch_body["task"]["status"] == "queued"
    assert fetch_body["task"]["payload"]["agent_id"] == "echo"
    assert fetch_body["task"]["payload"]["input"] == "hello queue"


def test_submit_generation_image_task_and_fetch():
    task_store_module._task_store = task_store_module.InMemoryTaskStore()

    submit_resp = client.post(
        "/api/v1/generation/image/submit",
        json={
            "prompt": "A futuristic AI-PaaS dashboard",
            "provider": "mock_image",
            "count": 2,
        },
    )

    assert submit_resp.status_code == 200
    submit_body = submit_resp.json()

    assert submit_body["success"] is True
    assert submit_body["task_type"] == "generation"
    assert submit_body["status"] == "queued"
    assert submit_body["queue_name"] == "generation"

    task_id = submit_body["task_id"]

    fetch_resp = client.get(f"/api/v1/tasks/{task_id}")
    assert fetch_resp.status_code == 200

    fetch_body = fetch_resp.json()
    assert fetch_body["task"]["payload"]["kind"] == "image"
    assert fetch_body["task"]["payload"]["provider"] == "mock_image"
    assert fetch_body["task"]["payload"]["count"] == 2


def test_submit_generation_video_task_and_fetch():
    task_store_module._task_store = task_store_module.InMemoryTaskStore()

    submit_resp = client.post(
        "/api/v1/generation/video/submit",
        json={
            "prompt": "A robot entering a smart factory",
            "provider": "seedance",
            "duration_seconds": 5,
            "resolution": "720p",
        },
    )

    assert submit_resp.status_code == 200
    submit_body = submit_resp.json()

    assert submit_body["success"] is True
    assert submit_body["task_type"] == "generation"
    assert submit_body["status"] == "queued"

    task_id = submit_body["task_id"]

    fetch_resp = client.get(f"/api/v1/tasks/{task_id}")
    assert fetch_resp.status_code == 200

    fetch_body = fetch_resp.json()
    assert fetch_body["task"]["payload"]["kind"] == "video"
    assert fetch_body["task"]["payload"]["provider"] == "seedance"
    assert fetch_body["task"]["payload"]["duration_seconds"] == 5
    assert fetch_body["task"]["payload"]["resolution"] == "720p"


def test_get_task_not_found():
    task_store_module._task_store = task_store_module.InMemoryTaskStore()

    response = client.get("/api/v1/tasks/not-found-id")
    assert response.status_code == 404
    body = response.json()
    assert "Task not found" in body["detail"]