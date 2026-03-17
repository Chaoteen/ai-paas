from __future__ import annotations

from bootstrap import runtime_bootstrap
from runtime.model_backed_llm_adapter import ModelBackedLLMAdapter
from runtime.runtime_metrics import InMemoryRuntimeMetrics
from runtime.trace_store import InMemoryTraceStore


def test_build_agent_runtime_injects_model_backed_llm_adapter() -> None:
    agent_runtime = runtime_bootstrap._build_agent_runtime(
        data_bus=None,
        trace_store=InMemoryTraceStore(),
        runtime_metrics=InMemoryRuntimeMetrics(),
    )

    assert isinstance(agent_runtime.llm_adapter, ModelBackedLLMAdapter)