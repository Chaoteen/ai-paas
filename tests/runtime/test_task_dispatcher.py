import pytest

from runtime.queue.task_dispatcher import TaskDispatchError, TaskDispatcher
from runtime.queue.task_models import AgentTaskPayload, TaskEnvelope
from runtime.queue.task_store import InMemoryTaskStore


class DummyQueue:
    def __init__(self) -> None:
        self.published = []

    async def publish_task(self, stream_name: str, task: TaskEnvelope) -> str:
        self.published.append((stream_name, task))
        return "msg-1"


class FailingQueue:
    async def publish_task(self, stream_name: str, task: TaskEnvelope) -> str:
        raise RuntimeError("redis publish failed")


def build_task() -> TaskEnvelope:
    return TaskEnvelope.for_agent(
        tenant_id="tenant-test",
        payload=AgentTaskPayload(
            prompt="hello",
            model="test-model",
        ),
    )


@pytest.mark.asyncio
async def test_dispatcher_persists_and_publishes() -> None:
    store = InMemoryTaskStore()
    queue = DummyQueue()
    dispatcher = TaskDispatcher(store=store, queue=queue)

    task = build_task()
    message_id = await dispatcher.dispatch(
        stream_name="agent_tasks",
        task=task,
    )

    assert message_id == "msg-1"
    assert len(queue.published) == 1

    published_stream, published_task = queue.published[0]
    assert published_stream == "agent_tasks"
    assert published_task.task_id == task.task_id
    assert published_task.status.value == "queued"

    saved = await store.get(task.task_id)
    assert saved is not None
    assert saved.task_id == task.task_id
    assert saved.status.value == "queued"


@pytest.mark.asyncio
async def test_dispatcher_marks_task_failed_when_publish_fails() -> None:
    store = InMemoryTaskStore()
    queue = FailingQueue()
    dispatcher = TaskDispatcher(store=store, queue=queue)

    task = build_task()

    with pytest.raises(TaskDispatchError):
        await dispatcher.dispatch(
            stream_name="agent_tasks",
            task=task,
        )

    saved = await store.get(task.task_id)
    assert saved is not None
    assert saved.task_id == task.task_id
    assert saved.status.value == "failed"
    assert saved.error is not None
    assert "redis publish failed" in saved.error