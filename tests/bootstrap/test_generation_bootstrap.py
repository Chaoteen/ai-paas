from __future__ import annotations

from bootstrap.generation_bootstrap import (
    build_generation_registry,
    build_generation_toolset,
)
from runtime.generation.types import GenerationProvider


def test_build_generation_registry_from_config() -> None:
    registry = build_generation_registry(
        config={
            "generation_models": [
                {
                    "provider": "mock_image",
                    "model_name": "mock-image-v1",
                    "capabilities": ["image"],
                    "aliases": ["image-default"],
                    "is_default": True,
                }
            ]
        }
    )

    model = registry.resolve_config("image-default")
    assert model.provider == GenerationProvider.MOCK_IMAGE
    assert model.model_name == "mock-image-v1"


def test_build_generation_toolset_from_default_registry(monkeypatch) -> None:
    monkeypatch.setenv("AI_PAAS_ENABLE_MOCK_IMAGE_PROVIDER", "true")
    toolset = build_generation_toolset()
    assert toolset.default_image_model_ref is None