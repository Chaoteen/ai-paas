from __future__ import annotations

import pytest

from bootstrap.runtime_bootstrap import build_runtime_state
from runtime.model_backed_llm_adapter import ModelBackedLLMAdapter


@pytest.mark.asyncio
async def test_build_runtime_state_memory_injects_model_backed_llm_adapter(monkeypatch) -> None:
    monkeypatch.setenv("AI_PAAS_PERSISTENCE", "memory")
    monkeypatch.setenv("AI_PAAS_EVENT_BUS", "memory")
    monkeypatch.delenv("AI_PAAS_OPENAI_ENDPOINT", raising=False)
    monkeypatch.delenv("AI_PAAS_OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("AI_PAAS_QWEN_ENDPOINT", raising=False)
    monkeypatch.delenv("AI_PAAS_QWEN_API_KEY", raising=False)
    monkeypatch.delenv("AI_PAAS_DEEPSEEK_ENDPOINT", raising=False)
    monkeypatch.delenv("AI_PAAS_DEEPSEEK_API_KEY", raising=False)

    state = await build_runtime_state()

    assert state["mode"] == "memory"
    assert "agent_runtime" in state
    assert isinstance(state["agent_runtime"].llm_adapter, ModelBackedLLMAdapter)
    assert state["trace_store"] is not None
    assert state["runtime_metrics"] is not None