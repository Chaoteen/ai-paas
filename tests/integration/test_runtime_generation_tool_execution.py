from __future__ import annotations

from types import SimpleNamespace

import pytest

from bootstrap import runtime_bootstrap
from runtime.execution_context import ExecutionContext
from runtime.skill_manifest import SkillManifest


@pytest.mark.asyncio
async def test_bootstrapped_agent_runtime_executes_generation_image_tool(monkeypatch) -> None:
    monkeypatch.setenv("AI_PAAS_ENABLE_MOCK_IMAGE_PROVIDER", "true")

    agent_runtime = runtime_bootstrap._build_agent_runtime(
        data_bus=None,
        trace_store=None,
        runtime_metrics=None,
    )

    context = ExecutionContext(
        task_id="task-gen-1",
        tenant_id="tenant-1",
        workflow_id="wf-1",
        correlation_id="corr-1",
        user_id="user-1",
        selected_agent_id="agent-1",
        required_capability="image_generation",
        workspace_root="/tmp/workspace",
        trace_id="trace-1",
        requested_capabilities=["image_generation"],
        allowed_capabilities=["image_generation"],
        secrets_scope=[],
        metadata={},
        input_payload={"prompt": "a futuristic AI command center"},
    )

    skill = SkillManifest(
        name="bootstrap_generation_skill",
        version="1.0.0",
        description="Bootstrap generation execution test skill",
        source="test",
        root_dir="/tmp/skill",
        use_cases=[],
        triggers=[],
        capabilities={"image_generation": True},
        inputs={},
        outputs={},
        execution={"type": "tool"},
        llm={},
        tools=[{"name": "generation.image", "routing_policy": "image_first"}],
        priority=100,
    )

    granted = SimpleNamespace(granted_capabilities=["image_generation"])

    result = await agent_runtime._execute_tool(
        context=context,
        skill=skill,
        granted=granted,
    )

    assert result["mode"] == "tool"
    assert result["tool_result"]["tool_name"] == "generation.image"
    assert result["tool_result"]["result"]["task_type"] == "image"
    assert result["granted_capabilities"] == ["image_generation"]