from __future__ import annotations

import pytest

from runtime.models.adapters.ollama_adapter import OllamaAdapter
from runtime.models.exceptions import ModelCapabilityError, ModelRequestValidationError
from runtime.models.types import (
    ChatMessage,
    MessageRole,
    ModelCapability,
    ModelConfig,
    ModelProvider,
    ModelRequest,
    ToolSpec,
)


def test_llm_adapter_requires_messages() -> None:
    adapter = OllamaAdapter(
        ModelConfig(
            provider=ModelProvider.OLLAMA,
            model_name="qwen3:14b",
            endpoint="http://127.0.0.1:11434/v1/chat/completions",
            capabilities=frozenset({ModelCapability.CHAT}),
        )
    )

    with pytest.raises(ModelRequestValidationError):
        adapter.validate_request(ModelRequest(messages=[]))


def test_llm_adapter_rejects_streaming_when_capability_missing() -> None:
    adapter = OllamaAdapter(
        ModelConfig(
            provider=ModelProvider.OLLAMA,
            model_name="qwen3:14b",
            endpoint="http://127.0.0.1:11434/v1/chat/completions",
            capabilities=frozenset({ModelCapability.CHAT}),
        )
    )

    request = ModelRequest(
        messages=[ChatMessage(role=MessageRole.USER, content="hello")],
        stream=True,
    )

    with pytest.raises(ModelCapabilityError):
        adapter.validate_request(request)


def test_llm_adapter_rejects_tools_when_capability_missing() -> None:
    adapter = OllamaAdapter(
        ModelConfig(
            provider=ModelProvider.OLLAMA,
            model_name="deepseek-r1:latest",
            endpoint="http://127.0.0.1:11434/v1/chat/completions",
            capabilities=frozenset({ModelCapability.CHAT}),
        )
    )

    request = ModelRequest(
        messages=[ChatMessage(role=MessageRole.USER, content="search weather")],
        tools=[
            ToolSpec(
                name="weather_lookup",
                description="lookup weather",
                parameters={
                    "type": "object",
                    "properties": {"city": {"type": "string"}},
                    "required": ["city"],
                },
            )
        ],
    )

    with pytest.raises(ModelCapabilityError):
        adapter.validate_request(request)


def test_llm_adapter_accepts_valid_request() -> None:
    adapter = OllamaAdapter(
        ModelConfig(
            provider=ModelProvider.OLLAMA,
            model_name="qwen3:14b",
            endpoint="http://127.0.0.1:11434/v1/chat/completions",
            capabilities=frozenset(
                {
                    ModelCapability.CHAT,
                    ModelCapability.STREAMING,
                    ModelCapability.TOOLS,
                }
            ),
        )
    )

    request = ModelRequest(
        messages=[ChatMessage(role=MessageRole.USER, content="hello")],
        stream=True,
        tools=[
            ToolSpec(
                name="echo_tool",
                description="echo input",
                parameters={"type": "object", "properties": {}},
            )
        ],
    )

    adapter.validate_request(request)