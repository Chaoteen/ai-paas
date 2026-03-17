import pytest

from bootstrap.runtime_bootstrap import build_runtime_state


class FakeRedisStreamBus:
    @classmethod
    def from_env(cls):
        return cls()

    def ensure_group(self, stream, group_name):
        return None

    def consume(self, **kwargs):
        return []

    def ack(self, stream, group_name, message_id):
        return 1

    def dead_letter(self, **kwargs):
        return "1-0"


@pytest.mark.asyncio
async def test_build_runtime_state_memory_mode_includes_agent_runtime(monkeypatch):
    monkeypatch.setenv("AI_PAAS_PERSISTENCE", "memory")
    monkeypatch.setenv("AI_PAAS_EVENT_BUS", "memory")

    state = await build_runtime_state()

    assert state["mode"] == "memory"
    assert state["agent_runtime"] is not None
    assert state["router_worker"] is None
    assert state["agent_worker"] is None


@pytest.mark.asyncio
async def test_build_runtime_state_wires_agent_runtime_into_agent_worker(monkeypatch):
    monkeypatch.setenv("AI_PAAS_PERSISTENCE", "memory")
    monkeypatch.setenv("AI_PAAS_EVENT_BUS", "redis")

    import bootstrap.runtime_bootstrap as rb

    monkeypatch.setattr(rb.RedisStreamBus, "from_env", FakeRedisStreamBus.from_env)

    state = await build_runtime_state()

    assert state["agent_runtime"] is not None
    assert state["router_worker"] is not None
    assert state["agent_worker"] is not None
    assert state["agent_worker"].agent_runtime is state["agent_runtime"]