import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from gateway.api.tasks import (
    get_task_read_store,
    router,
)
from runtime.queue.task_models import TaskEnvelope
from runtime.queue.task_store import InMemoryTaskStore


class DummySubmissionResult:
    def __init__(
        self,
        *,
        task_id: str,
        queue_name: str,
        stream_name: str,
        outbox_event_id: int,
        status: str,
    ) -> None:
        self.task_id = task_id
        self.queue_name = queue_name
        self.stream_name = stream_name
        self.outbox_event_id = outbox_event_id
        self.status = status


class DummySubmissionService:
    def __init__(self, store: InMemoryTaskStore) -> None:
        self._store = store
        self._next_outbox_event_id = 1

    async def submit_task(self, *, task: TaskEnvelope, stream_name: str):
        if task.status.value != "queued":
            task.mark_queued()
        await self._store.put(task)

        result = DummySubmissionResult(
            task_id=task.task_id,
            queue_name=task.queue_name,
            stream_name=stream_name,
            outbox_event_id=self._next_outbox_event_id,
            status=task.status.value,
        )
        self._next_outbox_event_id += 1
        return result


def _build_app_with_overrides() -> tuple[FastAPI, InMemoryTaskStore]:
    from gateway.api import tasks as tasks_api

    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    store = InMemoryTaskStore()
    submission_service = DummySubmissionService(store)

    async def override_read_store():
        return store

    async def override_submission_service():
        return submission_service

    app.dependency_overrides[get_task_read_store] = override_read_store
    app.dependency_overrides[tasks_api.get_task_submission_service] = (
        override_submission_service
    )

    return app, store


@pytest.mark.asyncio
async def test_submit_agent_task_and_fetch() -> None:
    app, _store = _build_app_with_overrides()
    client = TestClient(app)

    submit_resp = client.post(
        "/api/v1/agent/submit",
        json={
            "tenant_id": "tenant-a",
            "prompt": "hello",
            "model": "test-model",
        },
    )
    assert submit_resp.status_code == 202

    submit_body = submit_resp.json()
    task_id = submit_body["task_id"]

    assert submit_body["status"] == "queued"
    assert submit_body["queue_name"] == "agent_tasks"
    assert submit_body["stream_name"] == "agent_tasks"
    assert submit_body["durable"] is True
    assert isinstance(submit_body["outbox_event_id"], int)

    get_resp = client.get(f"/api/v1/tasks/{task_id}")
    assert get_resp.status_code == 200

    body = get_resp.json()
    assert body["task_id"] == task_id
    assert body["tenant_id"] == "tenant-a"
    assert body["task_type"] == "agent"
    assert body["queue_name"] == "agent_tasks"
    assert body["status"] == "queued"
    assert body["payload"]["prompt"] == "hello"
    assert body["payload"]["model"] == "test-model"


@pytest.mark.asyncio
async def test_submit_generation_image_task_and_fetch() -> None:
    app, _store = _build_app_with_overrides()
    client = TestClient(app)

    submit_resp = client.post(
        "/api/v1/generation/image/submit",
        json={
            "tenant_id": "tenant-b",
            "prompt": "draw a cat",
            "model": "image-model",
            "size": "1024x1024",
        },
    )
    assert submit_resp.status_code == 202

    submit_body = submit_resp.json()
    task_id = submit_body["task_id"]

    assert submit_body["status"] == "queued"
    assert submit_body["queue_name"] == "generation_tasks"
    assert submit_body["stream_name"] == "generation_tasks"
    assert submit_body["durable"] is True
    assert isinstance(submit_body["outbox_event_id"], int)

    get_resp = client.get(f"/api/v1/tasks/{task_id}")
    assert get_resp.status_code == 200

    body = get_resp.json()
    assert body["task_id"] == task_id
    assert body["tenant_id"] == "tenant-b"
    assert body["task_type"] == "generation"
    assert body["queue_name"] == "generation_tasks"
    assert body["status"] == "queued"
    assert body["payload"]["prompt"] == "draw a cat"
    assert body["payload"]["model"] == "image-model"
    assert body["payload"]["modality"] == "image"
    assert body["payload"]["size"] == "1024x1024"


@pytest.mark.asyncio
async def test_submit_generation_video_task_and_fetch() -> None:
    app, _store = _build_app_with_overrides()
    client = TestClient(app)

    submit_resp = client.post(
        "/api/v1/generation/video/submit",
        json={
            "tenant_id": "tenant-c",
            "prompt": "make a short video",
            "model": "video-model",
            "duration_seconds": 5,
        },
    )
    assert submit_resp.status_code == 202

    submit_body = submit_resp.json()
    task_id = submit_body["task_id"]

    assert submit_body["status"] == "queued"
    assert submit_body["queue_name"] == "generation_tasks"
    assert submit_body["stream_name"] == "generation_tasks"
    assert submit_body["durable"] is True
    assert isinstance(submit_body["outbox_event_id"], int)

    get_resp = client.get(f"/api/v1/tasks/{task_id}")
    assert get_resp.status_code == 200

    body = get_resp.json()
    assert body["task_id"] == task_id
    assert body["tenant_id"] == "tenant-c"
    assert body["task_type"] == "generation"
    assert body["queue_name"] == "generation_tasks"
    assert body["status"] == "queued"
    assert body["payload"]["prompt"] == "make a short video"
    assert body["payload"]["model"] == "video-model"
    assert body["payload"]["modality"] == "video"
    assert body["payload"]["duration_seconds"] == 5


@pytest.mark.asyncio
async def test_submit_workflow_task_and_fetch() -> None:
    app, _store = _build_app_with_overrides()
    client = TestClient(app)

    submit_resp = client.post(
        "/api/v1/workflow/submit",
        json={
            "tenant_id": "tenant-d",
            "workflow_key": "pricing.quote.flow",
            "workflow_version": "1.0.0",
            "input": {
                "customer_name": "Acme",
                "sku": "SOLAR-LIGHT-01",
            },
            "context": {
                "source": "crm",
            },
            "metadata": {
                "trace_id": "trace-001",
            },
            "trigger_source": "api",
        },
    )
    assert submit_resp.status_code == 202

    submit_body = submit_resp.json()
    task_id = submit_body["task_id"]

    assert submit_body["status"] == "queued"
    assert submit_body["queue_name"] == "workflow_tasks"
    assert submit_body["stream_name"] == "workflow_tasks"
    assert submit_body["durable"] is True
    assert isinstance(submit_body["outbox_event_id"], int)

    get_resp = client.get(f"/api/v1/tasks/{task_id}")
    assert get_resp.status_code == 200

    body = get_resp.json()
    assert body["task_id"] == task_id
    assert body["tenant_id"] == "tenant-d"
    assert body["task_type"] == "workflow"
    assert body["queue_name"] == "workflow_tasks"
    assert body["status"] == "queued"
    assert body["payload"]["workflow_key"] == "pricing.quote.flow"
    assert body["payload"]["workflow_version"] == "1.0.0"
    assert body["payload"]["input"]["customer_name"] == "Acme"
    assert body["payload"]["context"]["source"] == "crm"
    assert body["payload"]["metadata"]["trace_id"] == "trace-001"
    assert body["payload"]["trigger_source"] == "api"


@pytest.mark.asyncio
async def test_get_task_not_found() -> None:
    app, _store = _build_app_with_overrides()
    client = TestClient(app)

    response = client.get("/api/v1/tasks/not-found-id")
    assert response.status_code == 404

    body = response.json()
    assert "Task not found" in body["detail"]