from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from bootstrap import runtime_bootstrap
from runtime.execution_context import ExecutionContext
from runtime.runtime_metrics import InMemoryRuntimeMetrics
from runtime.skill_manifest import SkillManifest
from runtime.trace_store import InMemoryTraceStore


@pytest.mark.asyncio
@patch("runtime.models.adapters.ollama_adapter.requests.post")
async def test_bootstrapped_agent_runtime_executes_llm_via_model_layer(
    mock_post: Mock,
    monkeypatch,
) -> None:
    monkeypatch.setenv("AI_PAAS_OLLAMA_MODEL", "qwen3:14b")
    monkeypatch.setenv("AI_PAAS_OLLAMA_ENDPOINT", "http://127.0.0.1:11434/v1/chat/completions")
    monkeypatch.setenv("AI_PAAS_OLLAMA_TOOLS", "false")

    response = Mock()
    response.status_code = 200
    response.json.return_value = {
        "model": "qwen3:14b",
        "choices": [
            {
                "finish_reason": "stop",
                "message": {
                    "role": "assistant",
                    "content": "bootstrapped runtime response",
                },
            }
        ],
        "usage": {
            "prompt_tokens": 12,
            "completion_tokens": 8,
            "total_tokens": 20,
        },
    }
    mock_post.return_value = response

    agent_runtime = runtime_bootstrap._build_agent_runtime(
        data_bus=None,
        trace_store=InMemoryTraceStore(),
        runtime_metrics=InMemoryRuntimeMetrics(),
    )

    context = ExecutionContext(
        task_id="task-boot-1",
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

    skill = SkillManifest(
        name="bootstrap_llm_skill",
        version="1.0.0",
        description="Bootstrap model execution test skill",
        source="test",
        root_dir="/tmp/skill",
        use_cases=[],
        triggers=[],
        capabilities=["chat"],
        inputs={},
        outputs={},
        execution={"type": "llm"},
        llm={
            "provider": "ollama",
            "model": "qwen3:14b",
            "routing_policy": "local_first",
        },
        tools=[],
        priority=100,
    )

    granted = SimpleNamespace(granted_capabilities=["chat"])

    result = await agent_runtime._execute_llm(
        context=context,
        skill=skill,
        granted=granted,
    )

    assert result["mode"] == "llm"
    assert result["llm_result"]["provider"] == "ollama"
    assert result["llm_result"]["model"] == "qwen3:14b"
    assert result["llm_result"]["content"] == "bootstrapped runtime response"
    assert result["granted_capabilities"] == ["chat"]