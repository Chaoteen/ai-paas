from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

from runtime.models.adapters.deepseek_adapter import DeepSeekAdapter
from runtime.models.adapters.openai_adapter import OpenAIAdapter
from runtime.models.adapters.qwen_adapter import QwenAdapter
from runtime.models.exceptions import ModelAuthenticationError, ModelProviderError
from runtime.models.types import (
    ChatMessage,
    MessageRole,
    ModelCapability,
    ModelConfig,
    ModelProvider,
    ModelRequest,
)


def _build_openai_adapter() -> OpenAIAdapter:
    return OpenAIAdapter(
        ModelConfig(
            provider=ModelProvider.OPENAI,
            model_name="gpt-4o-mini",
            endpoint="https://api.openai.com/v1/chat/completions",
            api_key="test-openai-key",
            capabilities=frozenset({ModelCapability.CHAT, ModelCapability.TOOLS}),
        )
    )


def _build_qwen_adapter() -> QwenAdapter:
    return QwenAdapter(
        ModelConfig(
            provider=ModelProvider.QWEN,
            model_name="qwen-max",
            endpoint="https://dashscope-compatible.example.com/v1/chat/completions",
            api_key="test-qwen-key",
            capabilities=frozenset({ModelCapability.CHAT}),
        )
    )


def _build_deepseek_adapter() -> DeepSeekAdapter:
    return DeepSeekAdapter(
        ModelConfig(
            provider=ModelProvider.DEEPSEEK,
            model_name="deepseek-chat",
            endpoint="https://api.deepseek.com/chat/completions",
            api_key="test-deepseek-key",
            capabilities=frozenset({ModelCapability.CHAT, ModelCapability.TOOLS}),
        )
    )


@patch("runtime.models.adapters.openai_adapter.requests.post")
def test_openai_adapter_generate_success(mock_post: Mock) -> None:
    adapter = _build_openai_adapter()

    response = Mock()
    response.status_code = 200
    response.json.return_value = {
        "id": "chatcmpl-openai-1",
        "model": "gpt-4o-mini",
        "choices": [
            {
                "finish_reason": "stop",
                "message": {
                    "role": "assistant",
                    "content": "OpenAI response",
                },
            }
        ],
        "usage": {
            "prompt_tokens": 12,
            "completion_tokens": 9,
            "total_tokens": 21,
        },
    }
    mock_post.return_value = response

    result = adapter.generate(
        ModelRequest(messages=[ChatMessage(role=MessageRole.USER, content="hello")])
    )

    assert result.provider == ModelProvider.OPENAI
    assert result.message.content == "OpenAI response"

    headers = mock_post.call_args.kwargs["headers"]
    assert headers["Authorization"] == "Bearer test-openai-key"


@patch("runtime.models.adapters.openai_adapter.requests.post")
def test_qwen_adapter_generate_success(mock_post: Mock) -> None:
    adapter = _build_qwen_adapter()

    response = Mock()
    response.status_code = 200
    response.json.return_value = {
        "id": "chatcmpl-qwen-1",
        "model": "qwen-max",
        "choices": [
            {
                "finish_reason": "stop",
                "message": {
                    "role": "assistant",
                    "content": "Qwen response",
                },
            }
        ],
        "usage": {
            "prompt_tokens": 7,
            "completion_tokens": 6,
            "total_tokens": 13,
        },
    }
    mock_post.return_value = response

    result = adapter.generate(
        ModelRequest(messages=[ChatMessage(role=MessageRole.USER, content="hi")])
    )

    assert result.provider == ModelProvider.QWEN
    assert result.message.content == "Qwen response"


@patch("runtime.models.adapters.openai_adapter.requests.post")
def test_deepseek_adapter_generate_success(mock_post: Mock) -> None:
    adapter = _build_deepseek_adapter()

    response = Mock()
    response.status_code = 200
    response.json.return_value = {
        "id": "chatcmpl-deepseek-1",
        "model": "deepseek-chat",
        "choices": [
            {
                "finish_reason": "stop",
                "message": {
                    "role": "assistant",
                    "content": "DeepSeek response",
                },
            }
        ],
        "usage": {
            "prompt_tokens": 11,
            "completion_tokens": 10,
            "total_tokens": 21,
        },
    }
    mock_post.return_value = response

    result = adapter.generate(
        ModelRequest(messages=[ChatMessage(role=MessageRole.USER, content="hi")])
    )

    assert result.provider == ModelProvider.DEEPSEEK
    assert result.message.content == "DeepSeek response"


@patch("runtime.models.adapters.openai_adapter.requests.post")
def test_openai_adapter_auth_error(mock_post: Mock) -> None:
    adapter = _build_openai_adapter()

    response = Mock()
    response.status_code = 401
    response.text = "unauthorized"
    mock_post.return_value = response

    with pytest.raises(ModelAuthenticationError):
        adapter.generate(
            ModelRequest(messages=[ChatMessage(role=MessageRole.USER, content="hello")])
        )


@patch("runtime.models.adapters.openai_adapter.requests.post")
def test_openai_adapter_provider_error(mock_post: Mock) -> None:
    adapter = _build_openai_adapter()

    response = Mock()
    response.status_code = 500
    response.text = "internal error"
    mock_post.return_value = response

    with pytest.raises(ModelProviderError):
        adapter.generate(
            ModelRequest(messages=[ChatMessage(role=MessageRole.USER, content="hello")])
        )