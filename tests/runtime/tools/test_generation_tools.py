from __future__ import annotations

import pytest

from runtime.execution_context import ExecutionContext
from runtime.generation.types import (
    GenerationArtifact,
    GenerationProvider,
    GenerationResponse,
    GenerationTaskType,
)
from runtime.skill_manifest import SkillManifest
from runtime.tools.generation_tools import GenerationToolSet


class FakeGenerationService:
    def __init__(self) -> None:
        self.last_request = None
        self.last_context = None

    async def generate(self, *, request, context):
        self.last_request = request
        self.last_context = context
        return GenerationResponse(
            provider=GenerationProvider.MOCK_IMAGE
            if request.task_type == GenerationTaskType.IMAGE
            else GenerationProvider.SEEDANCE,
            model_name="mock-image-v1"
            if request.task_type == GenerationTaskType.IMAGE
            else "seedance-v1",
            task_type=request.task_type,
            artifacts=[
                GenerationArtifact(
                    uri="mock://artifact",
                    mime_type="image/png"
                    if request.task_type == GenerationTaskType.IMAGE
                    else "video/mp4",
                )
            ],
            raw_response={"ok": True},
            latency_ms=1,
        )


@pytest.mark.asyncio
async def test_generation_tools_generate_image() -> None:
    toolset = GenerationToolSet(
        generation_service=FakeGenerationService(),
        default_image_model_ref="image-default",
        default_video_model_ref="video-default",
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
        input_payload={"prompt": "a futuristic city"},
    )

    skill = SkillManifest(
        name="generate_image_skill",
        version="1.0.0",
        description="Generate image",
        source="test",
        root_dir="/tmp/skill",
        capabilities={"image_generation": True},
        execution={"type": "tool"},
        tools=[{"name": "generation.image", "width": 1024, "height": 1024}],
        llm={},
    )

    result = await toolset.execute(
        context=context,
        skill=skill,
        tool_name="generation.image",
        arguments={"input": {"prompt": "a futuristic city"}},
        granted_capabilities=["image_generation"],
    )

    assert result["tool_name"] == "generation.image"
    assert result["result"]["task_type"] == "image"
    assert result["result"]["artifacts"][0]["mime_type"] == "image/png"


@pytest.mark.asyncio
async def test_generation_tools_generate_video() -> None:
    toolset = GenerationToolSet(
        generation_service=FakeGenerationService(),
        default_image_model_ref="image-default",
        default_video_model_ref="video-default",
    )

    context = ExecutionContext(
        task_id="task-2",
        tenant_id="tenant-2",
        workflow_id="wf-2",
        correlation_id="corr-2",
        user_id="user-2",
        selected_agent_id="agent-2",
        required_capability="video_generation",
        workspace_root="/tmp",
        allowed_capabilities=["video_generation"],
        input_payload={"prompt": "a robot walking in neon rain"},
    )

    skill = SkillManifest(
        name="generate_video_skill",
        version="1.0.0",
        description="Generate video",
        source="test",
        root_dir="/tmp/skill",
        capabilities={"video_generation": True},
        execution={"type": "tool"},
        tools=[{"name": "generation.video", "duration_seconds": 5, "fps": 24}],
        llm={},
    )

    result = await toolset.execute(
        context=context,
        skill=skill,
        tool_name="generation.video",
        arguments={"input": {"prompt": "a robot walking in neon rain"}},
        granted_capabilities=["video_generation"],
    )

    assert result["tool_name"] == "generation.video"
    assert result["result"]["task_type"] == "video"
    assert result["result"]["artifacts"][0]["mime_type"] == "video/mp4"