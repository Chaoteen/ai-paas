from __future__ import annotations

from pathlib import Path
import textwrap

import pytest

from runtime.agent_runtime import AgentRuntime
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
async def test_agent_runtime_executes_tool_skill() -> None:
    data_bus = DummyDataBus()
    registry = SkillRegistry(
        bundled_dir="skills/bundled",
        local_dir=None,
        workspace_dir=None,
    )
    resolver = SkillResolver(registry)
    policy_engine = PolicyEngine()

    runtime = AgentRuntime(
        registry=registry,
        resolver=resolver,
        policy_engine=policy_engine,
        llm_adapter=NoopLLMAdapter(),
        tool_executor=ToolExecutor(),
        data_bus=data_bus,
    )

    context = ExecutionContext(
        task_id="task-tool-001",
        tenant_id="tenant-a",
        required_capability="echo",
        input_payload={"text": "hello runtime"},
    )

    result = await runtime.execute(context=context)

    assert result.status == "completed"
    assert result.skill_name == "echo"
    assert result.output["mode"] == "tool"
    assert result.output["tool_result"]["tool_name"] == "echo"

    event_types = [e["event_type"] for e in data_bus.events]
    assert "skill.selected" in event_types
    assert "tool.invoking" in event_types
    assert "tool.completed" in event_types


@pytest.mark.asyncio
async def test_agent_runtime_denies_unauthorized_capability(tmp_path: Path) -> None:
    skill_root = tmp_path / "bundled" / "net-skill"
    skill_root.mkdir(parents=True)

    (skill_root / "skill.yaml").write_text(
        textwrap.dedent(
            """
            name: net-skill
            version: "0.1.0"
            description: "Skill requiring network capability"
            use_cases: [network_test]
            triggers: [network_test]
            capabilities:
              network: true
              shell: false
              filesystem_read: false
              filesystem_write: false
              secrets: false
            execution:
              type: tool
            tools:
              - name: echo
            """
        ).strip(),
        encoding="utf-8",
    )
    (skill_root / "SKILL.md").write_text("# net-skill", encoding="utf-8")

    data_bus = DummyDataBus()
    registry = SkillRegistry(
        bundled_dir=str(tmp_path / "bundled"),
        local_dir=None,
        workspace_dir=None,
    )
    resolver = SkillResolver(registry)
    policy_engine = PolicyEngine()

    runtime = AgentRuntime(
        registry=registry,
        resolver=resolver,
        policy_engine=policy_engine,
        llm_adapter=NoopLLMAdapter(),
        tool_executor=ToolExecutor(),
        data_bus=data_bus,
    )

    context = ExecutionContext(
        task_id="task-policy-001",
        tenant_id="tenant-a",
        required_capability="network_test",
        input_payload={"text": "blocked"},
        allowed_capabilities=[],
    )

    result = await runtime.execute(context=context)

    assert result.status == "failed"
    assert "requires capabilities" in (result.error or "")
    assert "denied: network" in (result.error or "")

    event_types = [e["event_type"] for e in data_bus.events]
    assert "skill.selected" in event_types
    assert "security.denied" in event_types


@pytest.mark.asyncio
async def test_agent_runtime_executes_llm_skill(tmp_path: Path) -> None:
    skill_root = tmp_path / "bundled" / "summarize"
    skill_root.mkdir(parents=True)

    (skill_root / "skill.yaml").write_text(
        textwrap.dedent(
            """
            name: summarize
            version: "0.1.0"
            description: "Summarize input text"
            use_cases: [summarize]
            triggers: [summarize]
            capabilities:
              network: false
              shell: false
              filesystem_read: false
              filesystem_write: false
              secrets: false
            execution:
              type: llm
            llm:
              provider: noop
              model: noop-model
            """
        ).strip(),
        encoding="utf-8",
    )
    (skill_root / "SKILL.md").write_text("# summarize", encoding="utf-8")

    data_bus = DummyDataBus()
    registry = SkillRegistry(
        bundled_dir=str(tmp_path / "bundled"),
        local_dir=None,
        workspace_dir=None,
    )
    resolver = SkillResolver(registry)
    policy_engine = PolicyEngine()

    runtime = AgentRuntime(
        registry=registry,
        resolver=resolver,
        policy_engine=policy_engine,
        llm_adapter=NoopLLMAdapter(),
        tool_executor=ToolExecutor(),
        data_bus=data_bus,
    )

    context = ExecutionContext(
        task_id="task-llm-001",
        tenant_id="tenant-a",
        required_capability="summarize",
        input_payload={"text": "This is a long text to summarize."},
    )

    result = await runtime.execute(context=context)

    assert result.status == "completed"
    assert result.skill_name == "summarize"
    assert result.output["mode"] == "llm"
    assert "INPUT:" in result.output["prompt"]
    assert result.output["llm_result"]["provider"] == "noop"

    event_types = [e["event_type"] for e in data_bus.events]
    assert "skill.selected" in event_types
    assert "llm.invoking" in event_types
    assert "llm.completed" in event_types