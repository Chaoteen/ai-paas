from __future__ import annotations

from runtime.generation.adapters.mock_image_adapter import MockImageAdapter
from runtime.generation.adapters.seedance_adapter import SeedanceAdapter
from runtime.generation.generation_registry import GenerationRegistry
from runtime.generation.types import (
    GenerationCapability,
    GenerationConfig,
    GenerationProvider,
)


def test_generation_registry_registers_video_and_image_models() -> None:
    registry = GenerationRegistry()

    registry.register(
        config=GenerationConfig(
            provider=GenerationProvider.SEEDANCE,
            model_name="seedance-v1",
            endpoint="https://seedance.example.com/generate",
            api_key="seedance-key",
            capabilities=frozenset({GenerationCapability.VIDEO}),
        ),
        adapter_cls=SeedanceAdapter,
        aliases=["seedance-default"],
        is_default=True,
    )

    registry.register(
        config=GenerationConfig(
            provider=GenerationProvider.MOCK_IMAGE,
            model_name="mock-image-v1",
            capabilities=frozenset({GenerationCapability.IMAGE}),
        ),
        adapter_cls=MockImageAdapter,
        aliases=["image-default"],
        is_default=True,
    )

    assert registry.resolve_config("seedance-default").provider == GenerationProvider.SEEDANCE
    assert registry.resolve_config("image-default").provider == GenerationProvider.MOCK_IMAGE