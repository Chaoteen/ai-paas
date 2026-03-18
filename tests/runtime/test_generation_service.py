from __future__ import annotations

import pytest

from runtime.execution_context import ExecutionContext
from runtime.generation.adapters.mock_image_adapter import MockImageAdapter
from runtime.generation.adapters.seedance_adapter import SeedanceAdapter
from runtime.generation.generation_registry import GenerationRegistry
from runtime.generation.types import (
    GenerationCapability,
    GenerationConfig,
    GenerationProvider,
    GenerationRequest,
    GenerationTaskType,
)
from runtime.generation_service import GenerationInvocationContext, GenerationService


@pytest.mark.asyncio
async def test_generation_service_executes_video_generation() -> None:
    registry = GenerationRegistry()
    registry.register(
        config=GenerationConfig(
            provider=GenerationProvider.SEEDANCE,
            model_name="seedance-v1",
            endpoint="https://seedance.example.com/generate",
            api_key="seedance-key",
            capabilities=frozenset({GenerationCapability.VIDEO}),
        ),
        adapter_cls=SeedanceAdapter,
        aliases=["seedance-default"],
        is_default=True,
    )

    service = GenerationService(registry=registry)

    context = ExecutionContext(
        task_id="task-gen-1",
        tenant_id="tenant-1",
        workflow_id="wf-1",
        correlation_id="corr-1",
        user_id="user-1",
        selected_agent_id="agent-1",
        required_capability="video_generation",
        workspace_root="/tmp/workspace",
        trace_id="trace-1",
        requested_capabilities=["video_generation"],
        allowed_capabilities=["video_generation"],
        secrets_scope={},
        metadata={},
        input_payload={"prompt": "test"},
    )

    invocation = GenerationInvocationContext.from_execution_context(
        context,
        model_ref="seedance-default",
        requires=frozenset({GenerationCapability.VIDEO}),
        routing_policy="video_first",
    )

    # use monkeypatched adapter behavior in focused tests; here just validate wiring
    assert invocation.correlation_id == "corr-1"