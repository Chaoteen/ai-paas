from control_plane.agent_manifest import AgentManifest
from control_plane.agent_registry import AgentRegistry


def test_register_agent_publishes_control_events():
    registry = AgentRegistry()

    record = registry.register(
        AgentManifest(
            name="agent.code",
            version="1.0.0",
            vendor="ai-paas",
            capabilities=["code.generate"],
            supported_models=["qwen-8b"],
            endpoint="http://127.0.0.1:9001",
        )
    )

    events = registry.list_control_events(aggregate_id=record.agent_id)
    event_types = [e.event_type for e in events]

    assert "agent.registered" in event_types
    assert "agent.status.changed" in event_types


def test_heartbeat_publishes_event():
    registry = AgentRegistry()

    record = registry.register(
        AgentManifest(
            name="agent.summary",
            version="1.0.0",
            vendor="ai-paas",
            capabilities=["summary"],
            supported_models=["qwen-8b"],
            endpoint="http://127.0.0.1:9002",
        )
    )

    registry.heartbeat(record.agent_id)

    events = registry.list_control_events(aggregate_id=record.agent_id)
    event_types = [e.event_type for e in events]

    assert "agent.heartbeat" in event_types


def test_filter_events_by_type():
    registry = AgentRegistry()

    record = registry.register(
        AgentManifest(
            name="agent.translate",
            version="1.0.0",
            vendor="ai-paas",
            capabilities=["translate"],
            supported_models=["qwen-8b"],
            endpoint="http://127.0.0.1:9003",
        )
    )

    registry.heartbeat(record.agent_id)

    heartbeat_events = registry.list_control_events(
        aggregate_id=record.agent_id,
        event_type="agent.heartbeat",
    )

    assert len(heartbeat_events) == 1
    assert heartbeat_events[0].event_type == "agent.heartbeat"