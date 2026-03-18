from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from runtime.queue.redis_queue import RedisStreamQueueClient
from runtime.queue.task_models import (
    AgentTaskPayload,
    GenerationTaskKind,
    GenerationTaskPayload,
    TaskEnvelope,
    TaskStatus,
)
from runtime.queue.task_store import InMemoryTaskStore
from runtime.workers.agent_worker import AgentWorker
from runtime.workers.generation_worker import GenerationWorker


class FakeRedisStreamClient:
    def __init__(self) -> None:
        self.streams: Dict[str, List[tuple[str, Dict[str, Any]]]] = {}
        self.groups: set[tuple[str, str]] = set()
        self.acked: List[tuple[str, str, str]] = []
        self._counter = 0

    async def xadd(self, stream: str, fields: Dict[str, Any]) -> str:
        self._counter += 1
        message_id = f"{self._counter}-0"
        self.streams.setdefault(stream, []).append((message_id, dict(fields)))
        return message_id

    async def xgroup_create(
        self,
        name: str,
        groupname: str,
        id: str = "0",
        mkstream: bool = True,
    ) -> bool:
        key = (name, groupname)
        if key in self.groups:
            raise Exception("BUSYGROUP Consumer Group name already exists")
        self.groups.add(key)
        if mkstream and name not in self.streams:
            self.streams[name] = []
        return True

    async def xreadgroup(
        self,
        groupname: str,
        consumername: str,
        streams: Dict[str, str],
        count: int = 10,
        block: int = 1000,
    ):
        results = []
        for stream_name in streams.keys():
            entries = self.streams.get(stream_name, [])[:count]
            formatted = []
            for message_id, fields in entries:
                formatted.append((message_id, fields))
            if formatted:
                results.append((stream_name, formatted))
        return results

    async def xack(self, stream: str, groupname: str, message_id: str) -> int:
        self.acked.append((stream, groupname, message_id))
        return 1


class FakeAgentRuntime:
    def __init__(self) -> None:
        self.calls: List[Dict[str, Any]] = []

    async def execute(self, *, context, preferred_skill=None):
        self.calls.append(
            {
                "task_id": context.task_id,
                "tenant_id": context.tenant_id,
                "input_payload": context.input_payload,
                "preferred_skill": preferred_skill,
                "metadata": context.metadata,
            }
        )
        return {
            "success": True,
            "status": "completed",
            "output": {
                "mode": "tool",
                "tool_result": {
                    "tool_name": preferred_skill,
                    "status": "ok",
                },
            },
            "error": None,
        }


@dataclass
class FakeArtifact:
    uri: str
    mime_type: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FakeGenerationResponse:
    provider: str
    model_name: str
    task_type: str
    artifacts: List[FakeArtifact]
    latency_ms: int
    raw_response: Dict[str, Any]


class FakeGenerationService:
    def __init__(self) -> None:
        self.calls: List[Dict[str, Any]] = []

    async def generate(self, *, request, context):
        self.calls.append(
            {
                "prompt": request.prompt,
                "task_type": getattr(request.task_type, "value", request.task_type),
                "provider": getattr(context.provider, "value", context.provider),
                "model_ref": context.model_ref,
                "requires": sorted(getattr(x, "value", x) for x in context.requires),
                "routing_policy": context.routing_policy,
            }
        )
        return FakeGenerationResponse(
            provider="mock_image",
            model_name="mock-image-v1",
            task_type="image",
            artifacts=[
                FakeArtifact(
                    uri="mock://image/generated-1.png",
                    mime_type="image/png",
                    metadata={"prompt": request.prompt},
                )
            ],
            latency_ms=1,
            raw_response={"mock": True},
        )


def run(awaitable):
    import asyncio
    return asyncio.run(awaitable)


def make_agent_task() -> TaskEnvelope:
    payload = AgentTaskPayload(
        agent_id="echo",
        input="hello worker",
        tenant_id="tenant-a",
        user_id="user-a",
        correlation_id="corr-agent-1",
    )
    task = TaskEnvelope.new_agent_task(payload)
    task.mark_queued()
    return task


def make_generation_task() -> TaskEnvelope:
    payload = GenerationTaskPayload(
        kind=GenerationTaskKind.IMAGE,
        prompt="A futuristic AI-PaaS dashboard",
        provider="mock_image",
        tenant_id="tenant-a",
        correlation_id="corr-gen-1",
    )
    task = TaskEnvelope.new_generation_task(payload)
    task.mark_queued()
    return task


def test_agent_worker_processes_task_and_acks():
    fake_redis = FakeRedisStreamClient()
    queue = RedisStreamQueueClient(client=fake_redis)
    store = InMemoryTaskStore()
    runtime = FakeAgentRuntime()
    worker = AgentWorker(
        queue_client=queue,
        task_store=store,
        agent_runtime=runtime,
        consumer_name="agent-worker-test",
    )

    task = make_agent_task()
    message_id = run(queue.publish_task(task))
    run(worker.ensure_queue())

    processed = run(worker.poll_once())

    assert processed == 1
    stored = store.get(task.task_id)
    assert stored is not None
    assert stored.status == TaskStatus.SUCCEEDED
    assert stored.result is not None
    assert stored.result["output"]["mode"] == "tool"
    assert len(runtime.calls) == 1
    assert runtime.calls[0]["preferred_skill"] == "echo"
    assert runtime.calls[0]["input_payload"]["input"] == "hello worker"
    assert fake_redis.acked == [
        (queue.stream_name_for_queue("agent"), queue.consumer_group, message_id)
    ]


def test_generation_worker_processes_task_and_acks():
    fake_redis = FakeRedisStreamClient()
    queue = RedisStreamQueueClient(client=fake_redis)
    store = InMemoryTaskStore()
    service = FakeGenerationService()
    worker = GenerationWorker(
        queue_client=queue,
        task_store=store,
        generation_service=service,
        consumer_name="generation-worker-test",
    )

    task = make_generation_task()
    message_id = run(queue.publish_task(task))
    run(worker.ensure_queue())

    processed = run(worker.poll_once())

    assert processed == 1
    stored = store.get(task.task_id)
    assert stored is not None
    assert stored.status == TaskStatus.SUCCEEDED
    assert stored.result is not None
    assert stored.result["provider"] == "mock_image"
    assert stored.result["model"] == "mock-image-v1"
    assert stored.result["output"]["artifacts"][0]["uri"] == "mock://image/generated-1.png"
    assert len(service.calls) == 1
    assert service.calls[0]["task_type"] == "image"
    assert fake_redis.acked == [
        (queue.stream_name_for_queue("generation"), queue.consumer_group, message_id)
    ]


def test_agent_worker_marks_failed_on_exception_and_acks():
    class FailingAgentRuntime:
        async def execute(self, *, context, preferred_skill=None):
            raise RuntimeError("agent execution failed")

    fake_redis = FakeRedisStreamClient()
    queue = RedisStreamQueueClient(client=fake_redis)
    store = InMemoryTaskStore()
    worker = AgentWorker(
        queue_client=queue,
        task_store=store,
        agent_runtime=FailingAgentRuntime(),
        consumer_name="agent-worker-fail",
    )

    task = make_agent_task()
    message_id = run(queue.publish_task(task))
    run(worker.ensure_queue())

    processed = run(worker.poll_once())

    assert processed == 1
    stored = store.get(task.task_id)
    assert stored is not None
    assert stored.status == TaskStatus.FAILED
    assert stored.retry_count == 1
    assert stored.error["type"] == "RuntimeError"
    assert "agent execution failed" in stored.error["message"]
    assert fake_redis.acked == [
        (queue.stream_name_for_queue("agent"), queue.consumer_group, message_id)
    ]