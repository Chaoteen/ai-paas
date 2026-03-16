from data_plane.data_bus import DataBus, DATA_EVENTS_STREAM
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


def test_data_bus_router_success():
    bus = RedisStreamBus(FakeRedis())
    data_bus = DataBus(bus)

    envelope = data_bus.router_success(
        task_id="task-1",
        route_to="analysis",
        tenant_id="tenant-a",
        correlation_id="corr-1",
        extra={"confidence": 0.98},
    )

    assert envelope.stream == DATA_EVENTS_STREAM
    assert envelope.event_type == "router.success"
    assert envelope.payload["task_id"] == "task-1"
    assert envelope.payload["route_to"] == "analysis"
    assert envelope.payload["extra"]["confidence"] == 0.98


def test_data_bus_router_failed():
    bus = RedisStreamBus(FakeRedis())
    data_bus = DataBus(bus)

    envelope = data_bus.router_failed(
        task_id="task-2",
        error="no_route_found",
        tenant_id="tenant-a",
    )

    assert envelope.event_type == "router.failed"
    assert envelope.payload["task_id"] == "task-2"
    assert envelope.payload["error"] == "no_route_found"