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
        return "msg-123"


@pytest.mark.asyncio
async def test_submit_agent_task_returns_queue_message_id() -> None:
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

    response = client.post(
        "/api/v1/agent/submit",
        json={
            "tenant_id": "tenant-test",
            "prompt": "hello",
            "model": "test-model",
        },
    )

    assert response.status_code == 202
    body = response.json()

    assert "task_id" in body
    assert body["status"] == "queued"
    assert body["queue_name"] == "agent_tasks"
    assert body["queue_message_id"] == "msg-123"

    task = await store.get(body["task_id"])
    assert task is not None
    assert task.status.value == "queued"
    assert task.queue_name == "agent_tasks"