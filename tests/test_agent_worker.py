import pytest

from data_plane.agent_worker import AgentWorker
from runtime.agent_runtime import AgentRuntime
from runtime.llm_adapter import NoopLLMAdapter
from runtime.policy_engine import PolicyEngine
from runtime.skill_registry import SkillRegistry
from runtime.skill_resolver import SkillResolver
from runtime.tool_executor import ToolExecutor


class FakeAgentRegistry:
    def __init__(self, agents):
        self._agents = agents

    async def list_agents(self, tenant_id=None):
        if tenant_id is None:
            return self._agents
        return [x for x in self._agents if x.get("tenant_id") == tenant_id]


class FakeDataBus:
    def __init__(self):
        self.executing_events = []
        self.completed_events = []
        self.failed_events = []
        self.published_events = []

    async def task_executing(self, **kwargs):
        self.executing_events.append(kwargs)
        return kwargs

    async def task_completed(self, **kwargs):
        self.completed_events.append(kwargs)
        return kwargs

    async def task_failed(self, **kwargs):
        self.failed_events.append(kwargs)
        return kwargs

    async def publish(
        self,
        *,
        event_type,
        payload,
        source,
        tenant_id,
        correlation_id=None,
        task_id=None,
        workflow_id=None,
    ):
        event = {
            "event_type": event_type,
            "payload": payload,
            "source": source,
            "tenant_id": tenant_id,
            "correlation_id": correlation_id,
            "task_id": task_id,
            "workflow_id": workflow_id,
        }
        self.published_events.append(event)
        return event


class FakeEnvelope:
    def __init__(self, **kwargs):
        self.event_type = kwargs.get("event_type", "router.success")
        self.task_id = kwargs.get("task_id")
        self.workflow_id = kwargs.get("workflow_id")
        self.tenant_id = kwargs.get("tenant_id")
        self.correlation_id = kwargs.get("correlation_id")
        self.payload = kwargs.get("payload", {})


class FakeEventBus:
    def ensure_group(self, stream, group_name):
        return None

    def consume(self, **kwargs):
        return []

    def ack(self, stream, group_name, message_id):
        return 1

    def dead_letter(self, **kwargs):
        return "1-0"


def build_runtime(data_bus):
    registry = SkillRegistry(
        bundled_dir="skills/bundled",
        local_dir=None,
        workspace_dir=None,
    )
    resolver = SkillResolver(registry)
    policy_engine = PolicyEngine()
    return AgentRuntime(
        registry=registry,
        resolver=resolver,
        policy_engine=policy_engine,
        llm_adapter=NoopLLMAdapter(),
        tool_executor=ToolExecutor(),
        data_bus=data_bus,
    )


@pytest.mark.asyncio
async def test_agent_worker_completed_with_agent_runtime():
    registry = FakeAgentRegistry(
        [
            {
                "id": "agent_translation_001",
                "name": "translator-agent",
                "tenant_id": "tenant_a",
                "status": "healthy",
                "metadata": {},
            }
        ]
    )
    data_bus = FakeDataBus()
    runtime = build_runtime(data_bus)

    worker = AgentWorker(
        agent_registry=registry,
        data_bus=data_bus,
        event_bus=FakeEventBus(),
        agent_runtime=runtime,
    )

    envelope = FakeEnvelope(
        task_id="task_100",
        workflow_id="wf_100",
        tenant_id="tenant_a",
        correlation_id="corr_100",
        payload={
            "task_id": "task_100",
            "route_to": "agent_translation_001",
            "extra": {
                "selected_agent_id": "agent_translation_001",
                "selected_agent_name": "translator-agent",
                "required_capability": "echo",
                "input": {"text": "hello"},
                "metadata": {},
            },
        },
    )

    await worker._handle_envelope(envelope)

    assert len(data_bus.executing_events) == 1
    assert len(data_bus.completed_events) == 1
    assert len(data_bus.failed_events) == 0

    completed = data_bus.completed_events[0]
    assert completed["task_id"] == "task_100"
    assert completed["result"]["execution_mode"] == "runtime"
    assert completed["result"]["agent_id"] == "agent_translation_001"
    assert completed["result"]["runtime"]["skill_name"] == "echo"
    assert completed["result"]["output"]["mode"] == "tool"

    event_types = [e["event_type"] for e in data_bus.published_events]
    assert "skill.selected" in event_types
    assert "tool.invoking" in event_types
    assert "tool.completed" in event_types


@pytest.mark.asyncio
async def test_agent_worker_failed_when_agent_not_found():
    registry = FakeAgentRegistry([])
    data_bus = FakeDataBus()
    runtime = build_runtime(data_bus)

    worker = AgentWorker(
        agent_registry=registry,
        data_bus=data_bus,
        event_bus=FakeEventBus(),
        agent_runtime=runtime,
    )

    envelope = FakeEnvelope(
        task_id="task_101",
        workflow_id="wf_101",
        tenant_id="tenant_a",
        correlation_id="corr_101",
        payload={
            "task_id": "task_101",
            "route_to": "missing-agent",
            "extra": {
                "selected_agent_id": "missing-agent",
                "selected_agent_name": "missing-agent",
                "required_capability": "echo",
                "input": {"text": "hello"},
                "metadata": {},
            },
        },
    )

    await worker._handle_envelope(envelope)

    assert len(data_bus.executing_events) == 1
    assert len(data_bus.completed_events) == 0
    assert len(data_bus.failed_events) == 1
    assert data_bus.failed_events[0]["error"] == "AGENT_NOT_FOUND"


@pytest.mark.asyncio
async def test_agent_worker_failed_when_runtime_denied(tmp_path):
    skill_root = tmp_path / "bundled" / "net-skill"
    skill_root.mkdir(parents=True)

    (skill_root / "skill.yaml").write_text(
        """
name: "net-skill"
version: "0.1.0"
description: "Skill requiring network"
use_cases:
  - "network_test"
triggers:
  - "network_test"
capabilities:
  network: true
  shell: false
  filesystem_read: false
  filesystem_write: false
  secrets: false
execution:
  type: "tool"
tools:
  - name: "echo"
""".strip(),
        encoding="utf-8",
    )
    (skill_root / "SKILL.md").write_text("# net-skill", encoding="utf-8")

    registry = FakeAgentRegistry(
        [
            {
                "id": "agent_network_001",
                "name": "network-agent",
                "tenant_id": "tenant_a",
                "status": "healthy",
                "metadata": {},
            }
        ]
    )
    data_bus = FakeDataBus()

    runtime_registry = SkillRegistry(
        bundled_dir=str(tmp_path / "bundled"),
        local_dir=None,
        workspace_dir=None,
    )
    runtime = AgentRuntime(
        registry=runtime_registry,
        resolver=SkillResolver(runtime_registry),
        policy_engine=PolicyEngine(),
        llm_adapter=NoopLLMAdapter(),
        tool_executor=ToolExecutor(),
        data_bus=data_bus,
    )

    worker = AgentWorker(
        agent_registry=registry,
        data_bus=data_bus,
        event_bus=FakeEventBus(),
        agent_runtime=runtime,
    )

    envelope = FakeEnvelope(
        task_id="task_102",
        workflow_id="wf_102",
        tenant_id="tenant_a",
        correlation_id="corr_102",
        payload={
            "task_id": "task_102",
            "route_to": "agent_network_001",
            "extra": {
                "selected_agent_id": "agent_network_001",
                "selected_agent_name": "network-agent",
                "required_capability": "network_test",
                "input": {"text": "hello"},
                "metadata": {},
            },
        },
    )

    await worker._handle_envelope(envelope)

    assert len(data_bus.executing_events) == 1
    assert len(data_bus.completed_events) == 0
    assert len(data_bus.failed_events) == 1
    assert "unauthorized capabilities" in data_bus.failed_events[0]["error"]

    event_types = [e["event_type"] for e in data_bus.published_events]
    assert "skill.selected" in event_types
    assert "security.denied" in event_types