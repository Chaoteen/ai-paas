from types import SimpleNamespace

from fastapi.testclient import TestClient

from gateway.api.tasks import (
    get_task_store,
    get_task_submission_service,
)
from gateway.main import app
from runtime.queue.task_models import TaskEnvelope
from runtime.queue.task_store import InMemoryTaskStore


class FakeSubmissionService:
    def __init__(self, store: InMemoryTaskStore):
        self.store = store
        self.outbox_event_id = 0

    async def submit_task(self, *, task: TaskEnvelope, stream_name: str):
        task.mark_queued()
        await self.store.put(task)
        self.outbox_event_id += 1
        return SimpleNamespace(
            task_id=task.task_id,
            status=task.status.value,
            queue_name=task.queue_name,
            stream_name=stream_name,
            outbox_event_id=self.outbox_event_id,
        )


def _make_client():
    store = InMemoryTaskStore()
    submission_service = FakeSubmissionService(store)

    async def override_store():
        return store

    async def override_submission_service():
        return submission_service

    app.dependency_overrides[get_task_store] = override_store
    app.dependency_overrides[get_task_submission_service] = override_submission_service
    client = TestClient(app)
    return client


def teardown_function():
    app.dependency_overrides.clear()


def test_submit_agent_task_and_fetch():
    client = _make_client()

    submit_resp = client.post(
        "/api/v1/agent/submit",
        json={
            "tenant_id": "tenant-a",
            "prompt": "hello queue",
            "model": "qwen",
            "system_prompt": "You are helpful.",
            "temperature": 0.7,
            "max_tokens": 64,
            "metadata": {"source": "test"},
        },
    )

    assert submit_resp.status_code == 202
    submit_body = submit_resp.json()
    assert submit_body["status"] == "queued"
    assert submit_body["queue_name"] == "agent_tasks"
    assert submit_body["stream_name"] == "agent_tasks"
    assert submit_body["durable"] is True
    assert isinstance(submit_body["outbox_event_id"], int)

    task_id = submit_body["task_id"]

    fetch_resp = client.get(f"/api/v1/tasks/{task_id}")
    assert fetch_resp.status_code == 200
    fetch_body = fetch_resp.json()
    assert fetch_body["task_id"] == task_id
    assert fetch_body["task_type"] == "agent"
    assert fetch_body["status"] == "queued"
    assert fetch_body["payload"]["model"] == "qwen"
    assert fetch_body["payload"]["prompt"] == "hello queue"


def test_submit_generation_image_task_and_fetch():
    client = _make_client()

    submit_resp = client.post(
        "/api/v1/generation/image/submit",
        json={
            "tenant_id": "tenant-a",
            "prompt": "A futuristic AI-PaaS dashboard",
            "model": "mock-image",
            "size": "1024x1024",
            "metadata": {"source": "test"},
        },
    )

    assert submit_resp.status_code == 202
    submit_body = submit_resp.json()
    assert submit_body["status"] == "queued"
    assert submit_body["queue_name"] == "generation_tasks"

    task_id = submit_body["task_id"]

    fetch_resp = client.get(f"/api/v1/tasks/{task_id}")
    assert fetch_resp.status_code == 200
    fetch_body = fetch_resp.json()
    assert fetch_body["task_type"] == "generation"
    assert fetch_body["payload"]["modality"] == "image"
    assert fetch_body["payload"]["model"] == "mock-image"
    assert fetch_body["payload"]["size"] == "1024x1024"


def test_submit_generation_video_task_and_fetch():
    client = _make_client()

    submit_resp = client.post(
        "/api/v1/generation/video/submit",
        json={
            "tenant_id": "tenant-a",
            "prompt": "A robot entering a smart factory",
            "model": "mock-video",
            "duration_seconds": 5,
            "metadata": {"source": "test"},
        },
    )

    assert submit_resp.status_code == 202
    submit_body = submit_resp.json()
    assert submit_body["status"] == "queued"

    task_id = submit_body["task_id"]

    fetch_resp = client.get(f"/api/v1/tasks/{task_id}")
    assert fetch_resp.status_code == 200
    fetch_body = fetch_resp.json()
    assert fetch_body["payload"]["modality"] == "video"
    assert fetch_body["payload"]["model"] == "mock-video"
    assert fetch_body["payload"]["duration_seconds"] == 5


def test_get_task_not_found():
    client = _make_client()
    response = client.get("/api/v1/tasks/not-found-id")
    assert response.status_code == 404
    body = response.json()
    assert "Task not found" in body["detail"]