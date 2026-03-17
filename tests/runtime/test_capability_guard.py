import pytest

from runtime.agent_runtime import AgentRuntime
from runtime.capability_guard import CapabilityGuard
from runtime.execution_context import ExecutionContext
from runtime.llm_adapter import NoopLLMAdapter
from runtime.policy_engine import PolicyEngine
from runtime.skill_registry import SkillRegistry
from runtime.skill_resolver import SkillResolver
from runtime.tool_executor import ToolExecutor


class DummyDataBus:
    def __init__(self) -> None:
        self.events = []

    async def publish(
        self,
        *,
        event_type: str,
        payload: dict,
        source: str,
        tenant_id: str,
        correlation_id: str | None = None,
        task_id: str | None = None,
        workflow_id: str | None = None,
    ) -> dict:
        event = {
            "event_type": event_type,
            "payload": payload,
            "source": source,
            "tenant_id": tenant_id,
            "correlation_id": correlation_id,
            "task_id": task_id,
            "workflow_id": workflow_id,
        }
        self.events.append(event)
        return event


@pytest.mark.asyncio
async def test_capability_guard_allows_echo_skill_without_sensitive_caps():
    data_bus = DummyDataBus()
    registry = SkillRegistry(
        bundled_dir="skills/bundled",
        local_dir=None,
        workspace_dir=None,
    )

    runtime = AgentRuntime(
        registry=registry,
        resolver=SkillResolver(registry),
        policy_engine=PolicyEngine(),
        capability_guard=CapabilityGuard(),
        llm_adapter=NoopLLMAdapter(),
        tool_executor=ToolExecutor(),
        data_bus=data_bus,
    )

    context = ExecutionContext(
        task_id="task-echo-001",
        tenant_id="tenant-a",
        required_capability="echo",
        input_payload={"text": "hello"},
        allowed_capabilities=[],
    )

    result = await runtime.execute(context=context)

    assert result.status == "completed"
    assert result.skill_name == "echo"


@pytest.mark.asyncio
async def test_capability_guard_denies_network_skill(tmp_path):
    skill_root = tmp_path / "bundled" / "network-skill"
    skill_root.mkdir(parents=True)

    (skill_root / "skill.yaml").write_text(
        """
name: "network-skill"
version: "0.1.0"
description: "Requires outbound network"
use_cases:
  - "fetch_remote"
triggers:
  - "fetch_remote"
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
    (skill_root / "SKILL.md").write_text("# network-skill", encoding="utf-8")

    data_bus = DummyDataBus()
    registry = SkillRegistry(
        bundled_dir=str(tmp_path / "bundled"),
        local_dir=None,
        workspace_dir=None,
    )

    runtime = AgentRuntime(
        registry=registry,
        resolver=SkillResolver(registry),
        policy_engine=PolicyEngine(),
        capability_guard=CapabilityGuard(),
        llm_adapter=NoopLLMAdapter(),
        tool_executor=ToolExecutor(),
        data_bus=data_bus,
    )

    context = ExecutionContext(
        task_id="task-net-001",
        tenant_id="tenant-a",
        required_capability="fetch_remote",
        input_payload={"text": "hello"},
        allowed_capabilities=[],
    )

    result = await runtime.execute(context=context)

    assert result.status == "failed"
    assert "requires capabilities" in (result.error or "")

    event_types = [e["event_type"] for e in data_bus.events]
    assert "skill.selected" in event_types
    assert "security.denied" in event_types


@pytest.mark.asyncio
async def test_capability_guard_allows_network_skill_when_granted(tmp_path):
    skill_root = tmp_path / "bundled" / "network-skill"
    skill_root.mkdir(parents=True)

    (skill_root / "skill.yaml").write_text(
        """
name: "network-skill"
version: "0.1.0"
description: "Requires outbound network"
use_cases:
  - "fetch_remote"
triggers:
  - "fetch_remote"
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
    (skill_root / "SKILL.md").write_text("# network-skill", encoding="utf-8")

    data_bus = DummyDataBus()
    registry = SkillRegistry(
        bundled_dir=str(tmp_path / "bundled"),
        local_dir=None,
        workspace_dir=None,
    )

    runtime = AgentRuntime(
        registry=registry,
        resolver=SkillResolver(registry),
        policy_engine=PolicyEngine(),
        capability_guard=CapabilityGuard(),
        llm_adapter=NoopLLMAdapter(),
        tool_executor=ToolExecutor(),
        data_bus=data_bus,
    )

    context = ExecutionContext(
        task_id="task-net-002",
        tenant_id="tenant-a",
        required_capability="fetch_remote",
        input_payload={"text": "hello"},
        allowed_capabilities=["network"],
    )

    result = await runtime.execute(context=context)

    assert result.status == "completed"
    assert result.skill_name == "network-skill"