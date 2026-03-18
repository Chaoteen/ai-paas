from __future__ import annotations

import pytest

from runtime.execution_context import ExecutionContext
from runtime.skill_manifest import SkillManifest
from runtime.tool_executor import ToolExecutor
from runtime.tools.generation_tools import GenerationToolSet


class FakeGenerationService:
    async def generate(self, *, request, context):
        from runtime.generation.types import (
            GenerationArtifact,
            GenerationProvider,
            GenerationResponse,
        )

        return GenerationResponse(
            provider=GenerationProvider.MOCK_IMAGE,
            model_name="mock-image-v1",
            task_type=request.task_type,
            artifacts=[GenerationArtifact(uri="mock://artifact", mime_type="image/png")],
            raw_response={"ok": True},
            latency_ms=1,
        )


@pytest.mark.asyncio
async def test_tool_executor_routes_generation_image() -> None:
    executor = ToolExecutor(
        generation_tools=GenerationToolSet(
            generation_service=FakeGenerationService(),
            default_image_model_ref="image-default",
        )
    )

    context = ExecutionContext(
        task_id="task-1",
        tenant_id="tenant-1",
        workflow_id="wf-1",
        correlation_id="corr-1",
        user_id="user-1",
        selected_agent_id="agent-1",
        required_capability="image_generation",
        workspace_root="/tmp",
        allowed_capabilities=["image_generation"],
        input_payload={"prompt": "a futuristic workstation"},
    )

    skill = SkillManifest(
        name="generate_image_skill",
        version="1.0.0",
        description="Generate image",
        source="test",
        root_dir="/tmp/skill",
        capabilities={"image_generation": True},
        execution={"type": "tool"},
        tools=[{"name": "generation.image"}],
        llm={},
    )

    result = await executor.execute(
        context=context,
        skill=skill,
        tool_name="generation.image",
        arguments={"input": {"prompt": "a futuristic workstation"}},
    )

    assert result["status"] == "ok"
    assert result["tool_name"] == "generation.image"
    assert result["result"]["task_type"] == "image"