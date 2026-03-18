from __future__ import annotations

from unittest.mock import Mock, patch

from runtime.models.adapters.kimi_adapter import KimiAdapter
from runtime.models.types import (
    ChatMessage,
    MessageRole,
    ModelCapability,
    ModelConfig,
    ModelProvider,
    ModelRequest,
)


def _build_adapter() -> KimiAdapter:
    return KimiAdapter(
        ModelConfig(
            provider=ModelProvider.KIMI,
            model_name="kimi-k2.5",
            endpoint="https://kimi.example.com/v1/chat/completions",
            api_key="test-kimi-key",
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
def test_kimi_adapter_generate_success(mock_post: Mock) -> None:
    adapter = _build_adapter()

    response = Mock()
    response.status_code = 200
    response.json.return_value = {
        "model": "kimi-k2.5",
        "choices": [
            {
                "finish_reason": "stop",
                "message": {
                    "role": "assistant",
                    "content": "Kimi response",
                },
            }
        ],
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 6,
            "total_tokens": 16,
        },
    }
    mock_post.return_value = response

    result = adapter.generate(
        ModelRequest(
            messages=[ChatMessage(role=MessageRole.USER, content="hello kimi")]
        )
    )

    assert result.provider == ModelProvider.KIMI
    assert result.model_name == "kimi-k2.5"
    assert result.message.content == "Kimi response"

    headers = mock_post.call_args.kwargs["headers"]
    assert headers["Authorization"] == "Bearer test-kimi-key"