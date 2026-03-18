from __future__ import annotations

from runtime.generation.adapters.mock_image_adapter import MockImageAdapter
from runtime.generation.types import (
    GenerationCapability,
    GenerationConfig,
    GenerationProvider,
    GenerationRequest,
    GenerationTaskType,
)


def test_mock_image_adapter_generate_success() -> None:
    adapter = MockImageAdapter(
        GenerationConfig(
            provider=GenerationProvider.MOCK_IMAGE,
            model_name="mock-image-v1",
            capabilities=frozenset({GenerationCapability.IMAGE}),
        )
    )

    result = adapter.generate(
        GenerationRequest(
            task_type=GenerationTaskType.IMAGE,
            prompt="A futuristic AI workstation",
            width=1024,
            height=1024,
        )
    )

    assert result.provider == GenerationProvider.MOCK_IMAGE
    assert result.task_type == GenerationTaskType.IMAGE
    assert len(result.artifacts) == 1
    assert result.artifacts[0].mime_type == "image/png"