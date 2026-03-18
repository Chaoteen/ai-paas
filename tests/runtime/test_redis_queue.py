from __future__ import annotations

import json
from typing import Any, Dict, List, Tuple

from runtime.queue.redis_queue import PAYLOAD_FIELD, RedisStreamQueueClient
from runtime.queue.task_models import AgentTaskPayload, TaskEnvelope


class FakeRedisStreamClient:
    def __init__(self) -> None:
        self.streams: Dict[str, List[Tuple[str, Dict[str, Any]]]] = {}
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


def make_agent_task() -> TaskEnvelope:
    payload = AgentTaskPayload(
        agent_id="echo",
        input="hello queue",
        tenant_id="tenant-a",
        user_id="user-a",
        correlation_id="corr-123",
    )
    task = TaskEnvelope.new_agent_task(payload)
    task.mark_queued()
    return task


def test_publish_task_to_stream():
    fake = FakeRedisStreamClient()
    queue = RedisStreamQueueClient(client=fake)

    task = make_agent_task()
    message_id = run(queue.publish_task(task))

    assert message_id == "1-0"

    stream = queue.stream_name_for_queue("agent")
    assert stream in fake.streams
    assert len(fake.streams[stream]) == 1

    stored_message_id, stored_fields = fake.streams[stream][0]
    assert stored_message_id == "1-0"
    assert PAYLOAD_FIELD in stored_fields

    raw_payload = stored_fields[PAYLOAD_FIELD]
    data = json.loads(raw_payload)
    assert data["task_id"] == task.task_id
    assert data["task_type"] == "agent"
    assert data["payload"]["agent_id"] == "echo"


def test_ensure_consumer_group_is_idempotent():
    fake = FakeRedisStreamClient()
    queue = RedisStreamQueueClient(client=fake)

    run(queue.ensure_consumer_group("agent"))
    run(queue.ensure_consumer_group("agent"))

    stream = queue.stream_name_for_queue("agent")
    assert (stream, queue.consumer_group) in fake.groups


def test_read_tasks_from_stream():
    fake = FakeRedisStreamClient()
    queue = RedisStreamQueueClient(client=fake)

    task = make_agent_task()
    run(queue.publish_task(task))
    run(queue.ensure_consumer_group("agent"))

    messages = run(queue.read_tasks("agent", consumer_name="worker-1"))

    assert len(messages) == 1
    msg = messages[0]

    assert msg.stream == queue.stream_name_for_queue("agent")
    assert msg.message_id == "1-0"
    assert msg.task.task_id == task.task_id
    assert msg.task.task_type.value == "agent"
    assert msg.task.payload.agent_id == "echo"


def test_ack_task():
    fake = FakeRedisStreamClient()
    queue = RedisStreamQueueClient(client=fake)

    task = make_agent_task()
    message_id = run(queue.publish_task(task))
    run(queue.ensure_consumer_group("agent"))

    acked = run(queue.ack_task("agent", message_id))

    assert acked == 1
    assert fake.acked == [
        (queue.stream_name_for_queue("agent"), queue.consumer_group, message_id)
    ]


def run(awaitable):
    import asyncio

    return asyncio.run(awaitable)