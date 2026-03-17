from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

from runtime.models.adapters.ollama_adapter import OllamaAdapter
from runtime.models.exceptions import ModelProviderError
from runtime.models.types import (
    ChatMessage,
    MessageRole,
    ModelCapability,
    ModelConfig,
    ModelProvider,
    ModelRequest,
    ToolSpec,
)


def _build_adapter() -> OllamaAdapter:
    return OllamaAdapter(
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
            timeout_seconds=5.0,
        )
    )


@patch("runtime.models.adapters.ollama_adapter.requests.post")
def test_ollama_adapter_generate_success(mock_post: Mock) -> None:
    adapter = _build_adapter()

    response = Mock()
    response.status_code = 200
    response.json.return_value = {
        "id": "chatcmpl-local-1",
        "model": "qwen3:14b",
        "choices": [
            {
                "finish_reason": "stop",
                "message": {
                    "role": "assistant",
                    "content": "你好，这是本地模型的回复。",
                },
            }
        ],
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 8,
            "total_tokens": 18,
        },
    }
    mock_post.return_value = response

    result = adapter.generate(
        ModelRequest(
            messages=[ChatMessage(role=MessageRole.USER, content="你好")],
            temperature=0.2,
            max_tokens=128,
        )
    )

    assert result.provider == ModelProvider.OLLAMA
    assert result.model_name == "qwen3:14b"
    assert result.message.content == "你好，这是本地模型的回复。"
    assert result.usage.total_tokens == 18

    called_kwargs = mock_post.call_args.kwargs
    assert called_kwargs["json"]["model"] == "qwen3:14b"
    assert called_kwargs["json"]["temperature"] == 0.2
    assert called_kwargs["json"]["max_tokens"] == 128


@patch("runtime.models.adapters.ollama_adapter.requests.post")
def test_ollama_adapter_generate_with_tools(mock_post: Mock) -> None:
    adapter = _build_adapter()

    response = Mock()
    response.status_code = 200
    response.json.return_value = {
        "id": "chatcmpl-local-2",
        "model": "qwen3:14b",
        "choices": [
            {
                "finish_reason": "tool_calls",
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "type": "function",
                            "function": {
                                "name": "weather_lookup",
                                "arguments": "{\"city\":\"Singapore\"}",
                            },
                        }
                    ],
                },
            }
        ],
        "usage": {
            "prompt_tokens": 20,
            "completion_tokens": 5,
            "total_tokens": 25,
        },
    }
    mock_post.return_value = response

    result = adapter.generate(
        ModelRequest(
            messages=[ChatMessage(role=MessageRole.USER, content="查新加坡天气")],
            tools=[
                ToolSpec(
                    name="weather_lookup",
                    description="lookup weather by city",
                    parameters={
                        "type": "object",
                        "properties": {"city": {"type": "string"}},
                        "required": ["city"],
                    },
                )
            ],
        )
    )

    assert result.finish_reason == "tool_calls"
    assert len(result.message.tool_calls) == 1
    assert result.message.tool_calls[0].name == "weather_lookup"


@patch("runtime.models.adapters.ollama_adapter.requests.post")
def test_ollama_adapter_http_error_raises(mock_post: Mock) -> None:
    adapter = _build_adapter()

    response = Mock()
    response.status_code = 400
    response.text = '{"error":"model does not support tools"}'
    mock_post.return_value = response

    with pytest.raises(ModelProviderError):
        adapter.generate(
            ModelRequest(messages=[ChatMessage(role=MessageRole.USER, content="hello")])
        )