from control_plane.agent_manifest import AgentManifest
from control_plane.agent_registry import AgentRegistry


def test_register_agent_success():
    registry = AgentRegistry()

    manifest = AgentManifest(
        name="agent.code",
        version="1.0.0",
        vendor="ai-paas",
        capabilities=["code.generate", "code.refactor"],
        supported_models=["deepseek-r1", "qwen-8b"],
        endpoint="http://127.0.0.1:9001",
    )

    record = registry.register(manifest)

    assert record.agent_id.startswith("agt_")
    assert record.status == "online"
    assert record.manifest.name == "agent.code"
    assert record.last_heartbeat is not None


def test_register_agent_reject_invalid_endpoint():
    registry = AgentRegistry()

    manifest = AgentManifest(
        name="agent.bad",
        version="1.0.0",
        vendor="ai-paas",
        capabilities=["test"],
        supported_models=[],
        endpoint="tcp://127.0.0.1:9001",
    )

    try:
        registry.register(manifest)
        assert False, "expected ValueError"
    except ValueError as e:
        assert str(e) == "AGENT_ENDPOINT_INVALID_SCHEME"


def test_agent_heartbeat_updates_record():
    registry = AgentRegistry()

    manifest = AgentManifest(
        name="agent.summary",
        version="1.0.0",
        vendor="ai-paas",
        capabilities=["summary"],
        supported_models=["qwen-8b"],
        endpoint="http://127.0.0.1:9002",
    )

    record = registry.register(manifest)
    heartbeat_record = registry.heartbeat(record.agent_id)

    assert heartbeat_record.agent_id == record.agent_id
    assert heartbeat_record.status == "online"
    assert heartbeat_record.last_heartbeat is not None


def test_list_agents():
    registry = AgentRegistry()

    registry.register(
        AgentManifest(
            name="agent.a",
            version="1.0.0",
            vendor="ai-paas",
            capabilities=["a"],
            supported_models=[],
            endpoint="http://127.0.0.1:9101",
        )
    )
    registry.register(
        AgentManifest(
            name="agent.b",
            version="1.0.0",
            vendor="ai-paas",
            capabilities=["b"],
            supported_models=[],
            endpoint="http://127.0.0.1:9102",
        )
    )

    agents = registry.list_agents()
    assert len(agents) == 2
    assert agents[0].manifest.name == "agent.a"
    assert agents[1].manifest.name == "agent.b"