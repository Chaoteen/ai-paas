from __future__ import annotations

from unittest.mock import Mock, patch

from runtime.models.adapters.doubao_adapter import DoubaoAdapter
from runtime.models.types import (
    ChatMessage,
    MessageRole,
    ModelCapability,
    ModelConfig,
    ModelProvider,
    ModelRequest,
)


def _build_adapter() -> DoubaoAdapter:
    return DoubaoAdapter(
        ModelConfig(
            provider=ModelProvider.DOUBAO,
            model_name="doubao-seed-1-6",
            endpoint="https://volc.example.com/v1/chat/completions",
            api_key="test-doubao-key",
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
def test_doubao_adapter_generate_success(mock_post: Mock) -> None:
    adapter = _build_adapter()

    response = Mock()
    response.status_code = 200
    response.json.return_value = {
        "model": "doubao-seed-1-6",
        "choices": [
            {
                "finish_reason": "stop",
                "message": {
                    "role": "assistant",
                    "content": "Doubao response",
                },
            }
        ],
        "usage": {
            "prompt_tokens": 9,
            "completion_tokens": 5,
            "total_tokens": 14,
        },
    }
    mock_post.return_value = response

    result = adapter.generate(
        ModelRequest(
            messages=[ChatMessage(role=MessageRole.USER, content="hello doubao")]
        )
    )

    assert result.provider == ModelProvider.DOUBAO
    assert result.model_name == "doubao-seed-1-6"
    assert result.message.content == "Doubao response"