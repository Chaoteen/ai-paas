from data_plane.event_envelope import EventEnvelope


def test_event_envelope_roundtrip():
    envelope = EventEnvelope.new(
        event_type="router.success",
        stream="data.events",
        source="router",
        payload={"task_id": "task-1", "route_to": "analysis"},
        tenant_id="tenant-a",
        correlation_id="corr-123",
        headers={"x-test": "1"},
    )

    data = envelope.to_dict()
    restored = EventEnvelope.from_dict(data)

    assert restored.event_id == envelope.event_id
    assert restored.event_type == "router.success"
    assert restored.stream == "data.events"
    assert restored.source == "router"
    assert restored.payload["task_id"] == "task-1"
    assert restored.tenant_id == "tenant-a"
    assert restored.correlation_id == "corr-123"
    assert restored.headers["x-test"] == "1"