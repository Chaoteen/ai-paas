import pytest

from runtime.queue.task_models import (
    AgentTaskPayload,
    GenerationTaskPayload,
    TaskEnvelope,
)
from runtime.queue.task_store import InMemoryTaskStore
from runtime.workers.agent_worker import AgentWorker
from runtime.workers.generation_worker import GenerationWorker


class FakeQueue:
    def __init__(self, messages):
        self._messages = messages
        self.acked = []
        self.ensure_calls = []
        self.read_calls = []

    async def ensure_consumer_group(self, stream_name: str, group_name: str) -> None:
        self.ensure_calls.append((stream_name, group_name))

    async def read_tasks(
        self,
        *,
        stream_name: str,
        group_name: str,
        consumer_name: str,
        count: int = 1,
        block_ms: int = 1000,
    ):
        self.read_calls.append(
            (stream_name, group_name, consumer_name, count, block_ms)
        )
        return self._messages

    async def ack_task(
        self,
        *,
        stream_name: str,
        group_name: str,
        message_id: str,
    ) -> None:
        self.acked.append((stream_name, group_name, message_id))


def build_agent_task() -> TaskEnvelope:
    payload = AgentTaskPayload(
        prompt="hello agent",
        model="test-agent-model",
        metadata={"agent_id": "echo"},
    )
    return TaskEnvelope.for_agent(
        tenant_id="tenant-a",
        payload=payload,
        queue_name="agent_tasks",
        correlation_id="corr-agent-1",
    )


def build_generation_task(modality: str = "image") -> TaskEnvelope:
    payload = GenerationTaskPayload(
        prompt=f"generate {modality}",
        model="test-generation-model",
        modality=modality,
        metadata={"job": "demo"},
    )
    return TaskEnvelope.for_generation(
        tenant_id="tenant-b",
        payload=payload,
        queue_name="generation_tasks",
        correlation_id="corr-gen-1",
    )


@pytest.mark.asyncio
async def test_agent_worker_processes_task_successfully() -> None:
    task = build_agent_task()
    queue = FakeQueue(messages=[("msg-1", task)])
    store = InMemoryTaskStore()

    worker = AgentWorker(
        queue=queue,
        store=store,
        consumer_name="agent-worker-1",
    )

    async def fake_execute(task: TaskEnvelope):
        return {
            "output": f"processed: {task.payload['prompt']}",
            "model": task.payload["model"],
        }

    worker.execute_task = fake_execute  # type: ignore[method-assign]

    await worker.run_once()

    saved = await store.get(task.task_id)
    assert saved is not None
    assert saved.status.value == "succeeded"
    assert saved.result is not None
    assert saved.result["output"] == "processed: hello agent"
    assert saved.result["model"] == "test-agent-model"

    assert queue.acked == [("agent_tasks", worker.group_name, "msg-1")]
    assert queue.ensure_calls == [("agent_tasks", worker.group_name)]
    assert len(queue.read_calls) == 1


@pytest.mark.asyncio
async def test_agent_worker_marks_task_failed_on_execution_error() -> None:
    task = build_agent_task()
    queue = FakeQueue(messages=[("msg-2", task)])
    store = InMemoryTaskStore()

    worker = AgentWorker(
        queue=queue,
        store=store,
        consumer_name="agent-worker-1",
    )

    async def fake_execute(_task: TaskEnvelope):
        raise RuntimeError("agent execution failed")

    worker.execute_task = fake_execute  # type: ignore[method-assign]

    await worker.run_once()

    saved = await store.get(task.task_id)
    assert saved is not None
    assert saved.status.value == "failed"
    assert saved.error is not None
    assert "agent execution failed" in saved.error

    assert queue.acked == [("agent_tasks", worker.group_name, "msg-2")]


@pytest.mark.asyncio
async def test_generation_worker_processes_image_task_successfully() -> None:
    task = build_generation_task(modality="image")
    queue = FakeQueue(messages=[("msg-3", task)])
    store = InMemoryTaskStore()

    worker = GenerationWorker(
        queue=queue,
        store=store,
        consumer_name="generation-worker-1",
    )

    async def fake_execute(task: TaskEnvelope):
        return {
            "asset_url": "https://example.com/fake-image.png",
            "modality": task.payload["modality"],
        }

    worker.execute_task = fake_execute  # type: ignore[method-assign]

    await worker.run_once()

    saved = await store.get(task.task_id)
    assert saved is not None
    assert saved.status.value == "succeeded"
    assert saved.result is not None
    assert saved.result["asset_url"] == "https://example.com/fake-image.png"
    assert saved.result["modality"] == "image"

    assert queue.acked == [("generation_tasks", worker.group_name, "msg-3")]
    assert queue.ensure_calls == [("generation_tasks", worker.group_name)]


@pytest.mark.asyncio
async def test_generation_worker_marks_task_failed_on_execution_error() -> None:
    task = build_generation_task(modality="video")
    queue = FakeQueue(messages=[("msg-4", task)])
    store = InMemoryTaskStore()

    worker = GenerationWorker(
        queue=queue,
        store=store,
        consumer_name="generation-worker-1",
    )

    async def fake_execute(_task: TaskEnvelope):
        raise RuntimeError("generation execution failed")

    worker.execute_task = fake_execute  # type: ignore[method-assign]

    await worker.run_once()

    saved = await store.get(task.task_id)
    assert saved is not None
    assert saved.status.value == "failed"
    assert saved.error is not None
    assert "generation execution failed" in saved.error

    assert queue.acked == [("generation_tasks", worker.group_name, "msg-4")]