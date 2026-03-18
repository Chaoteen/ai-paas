from __future__ import annotations

from runtime.generation.adapters.mock_image_adapter import MockImageAdapter
from runtime.generation.adapters.seedance_adapter import SeedanceAdapter
from runtime.generation.generation_registry import GenerationRegistry
from runtime.generation.selector import GenerationSelectionInput, GenerationSelector
from runtime.generation.types import (
    GenerationCapability,
    GenerationConfig,
    GenerationProvider,
)


def _build_registry() -> GenerationRegistry:
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
    return registry


def test_generation_selector_video_first_prefers_seedance() -> None:
    selector = GenerationSelector(_build_registry())
    selected = selector.select(
        GenerationSelectionInput(
            requires=frozenset({GenerationCapability.VIDEO}),
            routing_policy="video_first",
        )
    )
    assert selected.provider == GenerationProvider.SEEDANCE


def test_generation_selector_image_first_prefers_mock_image() -> None:
    selector = GenerationSelector(_build_registry())
    selected = selector.select(
        GenerationSelectionInput(
            requires=frozenset({GenerationCapability.IMAGE}),
            routing_policy="image_first",
        )
    )
    assert selected.provider == GenerationProvider.MOCK_IMAGE