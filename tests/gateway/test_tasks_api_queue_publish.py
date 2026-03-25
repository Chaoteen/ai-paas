from types import SimpleNamespace

from fastapi.testclient import TestClient

from gateway.api.tasks import (
    get_task_store,
    get_task_submission_service,
)
from gateway.main import app
from runtime.queue.task_models import TaskEnvelope
from runtime.queue.task_store import InMemoryTaskStore


class RecordingSubmissionService:
    def __init__(self, store: InMemoryTaskStore):
        self.store = store
        self.calls = []
        self.outbox_event_id = 100

    async def submit_task(self, *, task: TaskEnvelope, stream_name: str):
        task.mark_queued()
        await self.store.put(task)
        self.calls.append(
            {
                "task_id": task.task_id,
                "stream_name": stream_name,
                "queue_name": task.queue_name,
                "task_type": task.task_type.value,
            }
        )
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
    submission_service = RecordingSubmissionService(store)

    async def override_store():
        return store

    async def override_submission_service():
        return submission_service

    app.dependency_overrides[get_task_store] = override_store
    app.dependency_overrides[get_task_submission_service] = override_submission_service
    client = TestClient(app)
    return client, submission_service


def teardown_function():
    app.dependency_overrides.clear()


def test_agent_submit_uses_agent_stream_name():
    client, submission_service = _make_client()

    response = client.post(
        "/api/v1/agent/submit",
        json={
            "tenant_id": "tenant-a",
            "prompt": "hello",
            "model": "qwen",
        },
    )

    assert response.status_code == 202
    body = response.json()
    assert body["stream_name"] == "agent_tasks"
    assert body["queue_name"] == "agent_tasks"
    assert body["durable"] is True

    assert len(submission_service.calls) == 1
    assert submission_service.calls[0]["stream_name"] == "agent_tasks"
    assert submission_service.calls[0]["task_type"] == "agent"


def test_generation_submit_uses_generation_stream_name():
    client, submission_service = _make_client()

    response = client.post(
        "/api/v1/generation/image/submit",
        json={
            "tenant_id": "tenant-a",
            "prompt": "draw a dashboard",
            "model": "mock-image",
        },
    )

    assert response.status_code == 202
    body = response.json()
    assert body["stream_name"] == "generation_tasks"
    assert body["queue_name"] == "generation_tasks"
    assert body["durable"] is True

    assert len(submission_service.calls) == 1
    assert submission_service.calls[0]["stream_name"] == "generation_tasks"
    assert submission_service.calls[0]["task_type"] == "generation"


def test_workflow_submit_uses_workflow_stream_name():
    client, submission_service = _make_client()

    response = client.post(
        "/api/v1/workflow/submit",
        json={
            "tenant_id": "tenant-a",
            "workflow_key": "pricing.quote.flow",
            "workflow_version": "1.0.0",
            "input": {
                "customer_name": "Acme",
            },
            "context": {
                "channel": "web",
            },
        },
    )

    assert response.status_code == 202
    body = response.json()
    assert body["stream_name"] == "workflow_tasks"
    assert body["queue_name"] == "workflow_tasks"
    assert body["durable"] is True

    assert len(submission_service.calls) == 1
    assert submission_service.calls[0]["stream_name"] == "workflow_tasks"
    assert submission_service.calls[0]["task_type"] == "workflow"