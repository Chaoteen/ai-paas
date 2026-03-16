import json

from data_plane.redis_stream_bus import RedisStreamBus


class FakeRedis:
    def __init__(self):
        self.streams = {}
        self.groups = {}
        self.acks = []
        self.seq = 0

    def ping(self):
        return True

    def xadd(self, stream, fields, maxlen=None, approximate=True):
        self.seq += 1
        msg_id = f"1-{self.seq}"
        self.streams.setdefault(stream, []).append((msg_id, fields))
        return msg_id

    def xgroup_create(self, stream, group_name, id="0", mkstream=True):
        if group_name in self.groups.get(stream, {}):
            raise Exception("BUSYGROUP Consumer Group name already exists")
        self.groups.setdefault(stream, {})[group_name] = {"last_id": id}
        self.streams.setdefault(stream, [])

    def xreadgroup(self, group_name, consumer_name, streams, count=10, block=1000):
        result = []
        for stream, cursor in streams.items():
            _ = cursor
            messages = self.streams.get(stream, [])[:count]
            if messages:
                result.append((stream, messages))
        return result

    def xack(self, stream, group_name, message_id):
        self.acks.append((stream, group_name, message_id))
        return 1


def test_publish_and_consume():
    fake_redis = FakeRedis()
    bus = RedisStreamBus(fake_redis)

    envelope = bus.publish_event(
        stream="data.events",
        event_type="router.success",
        source="router",
        payload={"task_id": "task-1", "route_to": "analysis"},
        tenant_id="tenant-1",
    )

    assert envelope.event_type == "router.success"
    assert envelope.stream == "data.events"

    bus.ensure_group("data.events", "router-group")
    messages = bus.consume(
        stream="data.events",
        group_name="router-group",
        consumer_name="consumer-1",
        count=10,
        block_ms=10,
    )

    assert len(messages) == 1
    assert messages[0].envelope.event_type == "router.success"
    assert messages[0].envelope.payload["task_id"] == "task-1"

    acked = bus.ack("data.events", "router-group", messages[0].message_id)
    assert acked == 1


def test_dead_letter():
    fake_redis = FakeRedis()
    bus = RedisStreamBus(fake_redis)

    envelope = bus.publish_event(
        stream="control.events",
        event_type="agent_registered",
        source="control_plane",
        payload={"agent_id": "agent-1"},
    )

    dlq_message_id = bus.dead_letter(
        original_stream="control.events",
        envelope=envelope,
        reason="handler_failed",
    )

    assert dlq_message_id == "1-2"
    assert "control.events.dlq" in fake_redis.streams

    msg_id, fields = fake_redis.streams["control.events.dlq"][0]
    _ = msg_id
    data = json.loads(fields["message"])
    assert data["headers"]["dead_letter"] is True
    assert data["payload"]["reason"] == "handler_failed"