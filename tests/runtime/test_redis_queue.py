import json
from typing import Any, Dict, List, Tuple

import pytest

from runtime.queue.redis_queue import RedisStreamQueueClient
from runtime.queue.task_models import AgentTaskPayload, TaskEnvelope


class FakeRedis:
    def __init__(self) -> None:
        self.xadd_calls: List[Tuple[str, Dict[str, Any]]] = []
        self.xgroup_create_calls: List[Tuple[str, str, str, bool]] = []
        self.xreadgroup_calls: List[Tuple[str, str, Dict[str, str], int, int]] = []
        self.xack_calls: List[Tuple[str, str, str]] = []
        self.group_created = False

    async def xadd(self, stream_name: str, fields: Dict[str, Any]) -> str:
        self.xadd_calls.append((stream_name, fields))
        return "msg-1"

    async def xgroup_create(
        self,
        name: str,
        groupname: str,
        id: str = "0",
        mkstream: bool = True,
    ) -> bool:
        self.xgroup_create_calls.append((name, groupname, id, mkstream))
        if self.group_created:
            raise Exception("BUSYGROUP Consumer Group name already exists")
        self.group_created = True
        return True

    async def xreadgroup(
        self,
        groupname: str,
        consumername: str,
        streams: Dict[str, str],
        count: int = 1,
        block: int = 1000,
    ):
        self.xreadgroup_calls.append(
            (groupname, consumername, streams, count, block)
        )
        task = make_agent_task()
        payload = task.model_dump(mode="json")
        return [
            (
                "agent_tasks",
                [
                    (
                        "msg-1",
                        {
                            "task": json.dumps(payload),
                        },
                    )
                ],
            )
        ]

    async def xack(self, stream_name: str, group_name: str, message_id: str) -> int:
        self.xack_calls.append((stream_name, group_name, message_id))
        return 1


def make_agent_task() -> TaskEnvelope:
    payload = AgentTaskPayload(
        prompt="hello from redis queue test",
        model="test-model",
        metadata={
            "agent_id": "echo",
            "input": "ping",
            "correlation_id": "corr-123",
        },
    )
    return TaskEnvelope.for_agent(
        tenant_id="tenant-test",
        payload=payload,
        queue_name="agent_tasks",
        correlation_id="corr-123",
    )


@pytest.mark.asyncio
async def test_publish_task_to_stream() -> None:
    fake_redis = FakeRedis()
    client = RedisStreamQueueClient(redis_client=fake_redis)

    task = make_agent_task()
    message_id = await client.publish_task("agent_tasks", task)

    assert message_id == "msg-1"
    assert len(fake_redis.xadd_calls) == 1

    stream_name, fields = fake_redis.xadd_calls[0]
    assert stream_name == "agent_tasks"
    assert "task" in fields

    raw_task = fields["task"]
    assert isinstance(raw_task, str)

    decoded = json.loads(raw_task)
    assert decoded["task_id"] == task.task_id
    assert decoded["tenant_id"] == "tenant-test"
    assert decoded["queue_name"] == "agent_tasks"
    assert decoded["task_type"] == "agent"
    assert decoded["payload"]["prompt"] == "hello from redis queue test"
    assert decoded["payload"]["model"] == "test-model"


@pytest.mark.asyncio
async def test_ensure_consumer_group_is_idempotent() -> None:
    fake_redis = FakeRedis()
    client = RedisStreamQueueClient(redis_client=fake_redis)

    await client.ensure_consumer_group("agent_tasks", "workers")
    await client.ensure_consumer_group("agent_tasks", "workers")

    assert len(fake_redis.xgroup_create_calls) == 2
    assert fake_redis.xgroup_create_calls[0] == (
        "agent_tasks",
        "workers",
        "0",
        True,
    )
    assert fake_redis.xgroup_create_calls[1] == (
        "agent_tasks",
        "workers",
        "0",
        True,
    )


@pytest.mark.asyncio
async def test_read_tasks_from_stream() -> None:
    fake_redis = FakeRedis()
    client = RedisStreamQueueClient(redis_client=fake_redis)

    messages = await client.read_tasks(
        stream_name="agent_tasks",
        group_name="workers",
        consumer_name="worker-1",
        count=10,
        block_ms=500,
    )

    assert len(messages) == 1

    message_id, task = messages[0]
    assert message_id == "msg-1"
    assert task.task_type.value == "agent"
    assert task.queue_name == "agent_tasks"
    assert task.payload["prompt"] == "hello from redis queue test"
    assert task.payload["model"] == "test-model"

    assert len(fake_redis.xreadgroup_calls) == 1
    assert fake_redis.xreadgroup_calls[0] == (
        "workers",
        "worker-1",
        {"agent_tasks": ">"},
        10,
        500,
    )


@pytest.mark.asyncio
async def test_ack_task() -> None:
    fake_redis = FakeRedis()
    client = RedisStreamQueueClient(redis_client=fake_redis)

    await client.ack_task(
        stream_name="agent_tasks",
        group_name="workers",
        message_id="msg-1",
    )

    assert len(fake_redis.xack_calls) == 1
    assert fake_redis.xack_calls[0] == (
        "agent_tasks",
        "workers",
        "msg-1",
    )