from __future__ import annotations

from unittest.mock import Mock, patch

from runtime.models.adapters.minimax_adapter import MiniMaxAdapter
from runtime.models.types import (
    ChatMessage,
    MessageRole,
    ModelCapability,
    ModelConfig,
    ModelProvider,
    ModelRequest,
)


def _build_adapter() -> MiniMaxAdapter:
    return MiniMaxAdapter(
        ModelConfig(
            provider=ModelProvider.MINIMAX,
            model_name="MiniMax-M2.5",
            endpoint="https://minimax.example.com/v1/chat/completions",
            api_key="test-minimax-key",
            capabilities=frozenset(
                {
                    ModelCapability.CHAT,
                    ModelCapability.TOOLS,
                    ModelCapability.JSON_MODE,
                    ModelCapability.STREAMING,
                }
            ),
        )
    )


@patch("runtime.models.adapters.openai_adapter.requests.post")
def test_minimax_adapter_generate_success(mock_post: Mock) -> None:
    adapter = _build_adapter()

    response = Mock()
    response.status_code = 200
    response.json.return_value = {
        "model": "MiniMax-M2.5",
        "choices": [
            {
                "finish_reason": "stop",
                "message": {
                    "role": "assistant",
                    "content": "MiniMax response",
                },
            }
        ],
        "usage": {
            "prompt_tokens": 12,
            "completion_tokens": 7,
            "total_tokens": 19,
        },
    }
    mock_post.return_value = response

    result = adapter.generate(
        ModelRequest(
            messages=[ChatMessage(role=MessageRole.USER, content="hello minimax")]
        )
    )

    assert result.provider == ModelProvider.MINIMAX
    assert result.model_name == "MiniMax-M2.5"
    assert result.message.content == "MiniMax response"