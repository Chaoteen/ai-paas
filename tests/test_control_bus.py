from control_plane.control_bus import ControlBus, CONTROL_EVENTS_STREAM
from data_plane.redis_stream_bus import RedisStreamBus


class FakeRedis:
    def __init__(self):
        self.streams = {}
        self.groups = {}
        self.seq = 0

    def ping(self):
        return True

    def xadd(self, stream, fields, maxlen=None, approximate=True):
        self.seq += 1
        msg_id = f"1-{self.seq}"
        self.streams.setdefault(stream, []).append((msg_id, fields))
        return msg_id

    def xgroup_create(self, stream, group_name, id="0", mkstream=True):
        self.groups.setdefault(stream, {})[group_name] = {"last_id": id}

    def xreadgroup(self, group_name, consumer_name, streams, count=10, block=1000):
        result = []
        for stream, _cursor in streams.items():
            msgs = self.streams.get(stream, [])[:count]
            if msgs:
                result.append((stream, msgs))
        return result

    def xack(self, stream, group_name, message_id):
        return 1


def test_control_bus_agent_registered():
    bus = RedisStreamBus(FakeRedis())
    control_bus = ControlBus(bus)

    envelope = control_bus.agent_registered(
        agent_id="agent-123",
        agent_name="summary-agent",
        tenant_id="tenant-1",
        metadata={"version": "v1"},
    )

    assert envelope.stream == CONTROL_EVENTS_STREAM
    assert envelope.event_type == "agent_registered"
    assert envelope.payload["agent_id"] == "agent-123"
    assert envelope.payload["agent_name"] == "summary-agent"
    assert envelope.payload["metadata"]["version"] == "v1"


def test_control_bus_status_changed():
    bus = RedisStreamBus(FakeRedis())
    control_bus = ControlBus(bus)

    envelope = control_bus.agent_status_changed(
        agent_id="agent-123",
        from_status="idle",
        to_status="running",
        tenant_id="tenant-1",
    )

    assert envelope.event_type == "agent_status_changed"
    assert envelope.payload["from_status"] == "idle"
    assert envelope.payload["to_status"] == "running"