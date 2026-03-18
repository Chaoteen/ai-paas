from __future__ import annotations

from unittest.mock import Mock, patch

from runtime.generation.adapters.seedance_adapter import SeedanceAdapter
from runtime.generation.types import (
    GenerationCapability,
    GenerationConfig,
    GenerationProvider,
    GenerationRequest,
    GenerationTaskType,
)


def _build_adapter() -> SeedanceAdapter:
    return SeedanceAdapter(
        GenerationConfig(
            provider=GenerationProvider.SEEDANCE,
            model_name="seedance-v1",
            endpoint="https://seedance.example.com/generate",
            api_key="seedance-key",
            capabilities=frozenset({GenerationCapability.VIDEO}),
        )
    )


@patch("runtime.generation.adapters.seedance_adapter.requests.post")
def test_seedance_adapter_generate_success(mock_post: Mock) -> None:
    adapter = _build_adapter()

    response = Mock()
    response.status_code = 200
    response.json.return_value = {
        "model": "seedance-v1",
        "artifacts": [
            {
                "uri": "https://cdn.example.com/out/video1.mp4",
                "mime_type": "video/mp4",
            }
        ],
    }
    mock_post.return_value = response

    result = adapter.generate(
        GenerationRequest(
            task_type=GenerationTaskType.VIDEO,
            prompt="A robot walking in neon rain",
            duration_seconds=5,
            fps=24,
        )
    )

    assert result.provider == GenerationProvider.SEEDANCE
    assert result.task_type == GenerationTaskType.VIDEO
    assert len(result.artifacts) == 1
    assert result.artifacts[0].mime_type == "video/mp4"