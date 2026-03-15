from control_plane.agent_manifest import AgentManifest, AgentRecord
from control_plane.control_events import ControlEvent
from control_plane.repositories.agent_repository import InMemoryAgentRepository
from control_plane.repositories.control_event_repository import InMemoryControlEventRepository


def test_inmemory_agent_repository_save_and_get():
    repo = InMemoryAgentRepository()

    record = AgentRecord.new(
        AgentManifest(
            name="agent.a",
            version="1.0.0",
            vendor="ai-paas",
            endpoint="http://127.0.0.1:9001",
        )
    )
    repo.save(record)

    loaded = repo.get(record.agent_id)
    assert loaded is not None
    assert loaded.agent_id == record.agent_id
    assert loaded.manifest.name == "agent.a"


def test_inmemory_agent_repository_get_by_name():
    repo = InMemoryAgentRepository()

    record = AgentRecord.new(
        AgentManifest(
            name="agent.lookup",
            version="1.0.0",
            vendor="ai-paas",
            endpoint="http://127.0.0.1:9002",
        )
    )
    repo.save(record)

    loaded = repo.get_by_name("agent.lookup")
    assert loaded is not None
    assert loaded.agent_id == record.agent_id


def test_inmemory_control_event_repository_save_and_filter():
    repo = InMemoryControlEventRepository()

    evt1 = ControlEvent.new(
        event_type="agent.registered",
        aggregate_type="agent",
        aggregate_id="agt_1",
    )
    evt2 = ControlEvent.new(
        event_type="agent.heartbeat",
        aggregate_type="agent",
        aggregate_id="agt_1",
    )
    evt3 = ControlEvent.new(
        event_type="agent.registered",
        aggregate_type="agent",
        aggregate_id="agt_2",
    )

    repo.save(evt1)
    repo.save(evt2)
    repo.save(evt3)

    assert repo.count() == 3
    assert len(repo.list_events(event_type="agent.registered")) == 2
    assert len(repo.list_events(aggregate_id="agt_1")) == 2
    assert len(repo.list_events(event_type="agent.heartbeat", aggregate_id="agt_1")) == 1