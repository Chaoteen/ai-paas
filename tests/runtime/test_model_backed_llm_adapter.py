from __future__ import annotations

from runtime.execution_context import ExecutionContext
from runtime.model_backed_llm_adapter import ModelBackedLLMAdapter
from runtime.model_service import ModelInvocationContext
from runtime.skill_manifest import SkillManifest
from runtime.models.types import (
    ChatMessage,
    MessageRole,
    ModelCapability,
    ModelProvider,
    ModelResponse,
    UsageInfo,
)


class FakeModelService:
    def __init__(self) -> None:
        self.last_request = None
        self.last_context = None

    def generate(self, *, request, context):
        self.last_request = request
        self.last_context = context
        return ModelResponse(
            provider=ModelProvider.OLLAMA,
            model_name="qwen3:14b",
            message=ChatMessage(
                role=MessageRole.ASSISTANT,
                content="fake response",
            ),
            finish_reason="stop",
            usage=UsageInfo(prompt_tokens=10, completion_tokens=5, total_tokens=15),
            latency_ms=8,
        )


def test_model_backed_llm_adapter_uses_runtime_aligned_fields() -> None:
    adapter = ModelBackedLLMAdapter(
        model_service=FakeModelService(),
        default_model_ref="default",
    )

    context = ExecutionContext(
        task_id="task-1",
        tenant_id="tenant-1",
        workflow_id="wf-1",
        correlation_id="corr-1",
        user_id="user-1",
        selected_agent_id="agent-1",
        required_capability="chat",
        workspace_root="/tmp/workspace",
        trace_id="trace-1",
        requested_capabilities=["chat"],
        allowed_capabilities=["chat"],
        secrets_scope={},
        metadata={"source": "test"},
        input_payload={"text": "hello"},
    )

    skill = SkillManifest(
        name="chat_skill",
        version="1.0.0",
        description="Chat skill",
        source="local",
        root_dir="/tmp/skill",
        use_cases=[],
        triggers=[],
        capabilities=["chat"],
        inputs={},
        outputs={},
        execution={"type": "llm"},
        llm={"provider": "ollama", "model": "qwen3:14b"},
        tools=[],
        priority=100,
    )

    import asyncio

    result = asyncio.run(
        adapter.generate(
            context=context,
            skill=skill,
            prompt="Hello runtime",
            config=skill.llm,
        )
    )

    assert result["provider"] == "ollama"
    assert result["model"] == "qwen3:14b"
    assert result["content"] == "fake response"

    assert adapter.model_service.last_context.task_id == "task-1"
    assert adapter.model_service.last_context.tenant_id == "tenant-1"
    assert adapter.model_service.last_context.workflow_id == "wf-1"
    assert adapter.model_service.last_context.correlation_id == "corr-1"
    assert adapter.model_service.last_context.user_id == "user-1"

    assert len(adapter.model_service.last_request.messages) == 1
    assert adapter.model_service.last_request.messages[0].content == "Hello runtime"


def test_model_backed_llm_adapter_resolves_provider_model_ref() -> None:
    adapter = ModelBackedLLMAdapter(
        model_service=FakeModelService(),
        default_model_ref="default",
    )

    context = ExecutionContext(
        task_id="task-2",
        tenant_id="tenant-2",
        workflow_id="wf-2",
        correlation_id="corr-2",
        user_id="user-2",
        selected_agent_id="agent-2",
        required_capability="chat",
        workspace_root="/tmp/workspace",
        trace_id="trace-2",
        requested_capabilities=["chat"],
        allowed_capabilities=["chat"],
        secrets_scope={},
        metadata={},
        input_payload={"text": "hello"},
    )

    skill = SkillManifest(
        name="chat_skill",
        version="1.0.0",
        description="Chat skill",
        source="local",
        root_dir="/tmp/skill",
        use_cases=[],
        triggers=[],
        capabilities=["chat"],
        inputs={},
        outputs={},
        execution={"type": "llm"},
        llm={"provider": "openai", "model": "gpt-4o-mini"},
        tools=[],
        priority=100,
    )

    import asyncio

    asyncio.run(
        adapter.generate(
            context=context,
            skill=skill,
            prompt="Hello runtime",
            config=skill.llm,
        )
    )

    assert adapter.model_service.last_context.model_ref == "openai:gpt-4o-mini"
    assert adapter.model_service.last_context.provider == ModelProvider.OPENAI