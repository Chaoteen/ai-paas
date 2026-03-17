from __future__ import annotations

from runtime.agent_runtime import AgentRuntime
from runtime.capability_guard import CapabilityGuard
from runtime.execution_context import ExecutionContext
from runtime.policy_engine import PolicyEngine
from runtime.skill_manifest import SkillManifest
from runtime.skill_registry import SkillRegistry
from runtime.skill_resolver import SkillResolver


class FakeLLMAdapter:
    async def generate(self, *, context, skill, prompt, config):
        return {
            "provider": config.get("provider", "ollama"),
            "model": config.get("model", "qwen3:14b"),
            "content": f"echo::{prompt}",
            "finish_reason": "stop",
            "tool_calls": [],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15,
            },
            "latency_ms": 7,
        }


class FakeResolver:
    def resolve(self, *, context, preferred_skill=None):
        return SkillManifest(
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


class FakePolicyDecision:
    def __init__(self):
        self.allowed = True
        self.reasons = []
        self.granted_capabilities = ["chat"]


class FakePolicyEngine:
    def evaluate(self, *, context, skill):
        return FakePolicyDecision()


class FakeCapabilityDecision:
    def __init__(self):
        self.allowed = True
        self.reasons = []
        self.required_capabilities = ["chat"]
        self.denied_capabilities = []
        self.granted_capabilities = ["chat"]


class FakeCapabilityGuard:
    def evaluate(self, *, context, skill):
        return FakeCapabilityDecision()


def test_agent_runtime_existing_contract_still_works_with_llm_adapter() -> None:
    runtime = AgentRuntime(
        registry=None,  # unused by FakeResolver path in this test
        resolver=FakeResolver(),
        policy_engine=FakePolicyEngine(),
        capability_guard=FakeCapabilityGuard(),
        llm_adapter=FakeLLMAdapter(),
        tool_executor=None,
        data_bus=None,
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
        metadata={},
        input_payload={"text": "hello"},
    )

    import asyncio

    result = asyncio.run(runtime.execute(context=context))

    assert result.status == "completed"
    assert result.skill_name == "chat_skill"
    assert result.output["mode"] == "llm"
    assert result.output["llm_result"]["provider"] == "ollama"
    assert result.output["llm_result"]["model"] == "qwen3:14b"