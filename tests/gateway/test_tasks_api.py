import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from gateway.api.tasks import (
    get_dispatch_queue,
    get_task_store,
    router,
)
from runtime.queue.task_store import (
    InMemoryTaskStore,
    reset_task_store,
    set_task_store,
)


class DummyQueue:
    async def publish_task(self, stream_name: str, task) -> str:
        return f"{stream_name}-msg-1"


@pytest.mark.asyncio
async def test_submit_agent_task_and_fetch() -> None:
    app = FastAPI()
    app.include_router(router)

    store = InMemoryTaskStore()
    await reset_task_store()
    await set_task_store(store)

    async def override_store():
        return store

    async def override_queue():
        return DummyQueue()

    app.dependency_overrides[get_task_store] = override_store
    app.dependency_overrides[get_dispatch_queue] = override_queue

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
    assert submit_body["queue_message_id"] == "agent_tasks-msg-1"

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
    app = FastAPI()
    app.include_router(router)

    store = InMemoryTaskStore()
    await reset_task_store()
    await set_task_store(store)

    async def override_store():
        return store

    async def override_queue():
        return DummyQueue()

    app.dependency_overrides[get_task_store] = override_store
    app.dependency_overrides[get_dispatch_queue] = override_queue

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
    assert submit_body["queue_message_id"] == "generation_tasks-msg-1"

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
    app = FastAPI()
    app.include_router(router)

    store = InMemoryTaskStore()
    await reset_task_store()
    await set_task_store(store)

    async def override_store():
        return store

    async def override_queue():
        return DummyQueue()

    app.dependency_overrides[get_task_store] = override_store
    app.dependency_overrides[get_dispatch_queue] = override_queue

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
    assert submit_body["queue_message_id"] == "generation_tasks-msg-1"

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
async def test_get_task_not_found() -> None:
    app = FastAPI()
    app.include_router(router)

    store = InMemoryTaskStore()
    await reset_task_store()
    await set_task_store(store)

    async def override_store():
        return store

    async def override_queue():
        return DummyQueue()

    app.dependency_overrides[get_task_store] = override_store
    app.dependency_overrides[get_dispatch_queue] = override_queue

    client = TestClient(app)

    response = client.get("/api/v1/tasks/not-found-id")
    assert response.status_code == 404

    body = response.json()
    assert "Task not found" in body["detail"]