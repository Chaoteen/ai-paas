from __future__ import annotations

import os
from typing import Any, Dict, Optional

from runtime.generation.adapters.mock_image_adapter import MockImageAdapter
from runtime.generation.adapters.seedance_adapter import SeedanceAdapter
from runtime.generation.generation_registry import GenerationRegistry
from runtime.generation.types import (
    GenerationCapability,
    GenerationConfig,
    GenerationProvider,
)
from runtime.generation_service import GenerationService
from runtime.tools.generation_tools import GenerationToolSet


def build_generation_registry(
    config: Optional[Dict[str, Any]] = None,
) -> GenerationRegistry:
    registry = GenerationRegistry()
    config = config or {}

    model_definitions = config.get("generation_models", [])
    if model_definitions:
        for item in model_definitions:
            provider = GenerationProvider(item["provider"])
            capabilities = frozenset(
                GenerationCapability(value) for value in item.get("capabilities", [])
            )

            adapter_cls = {
                GenerationProvider.SEEDANCE: SeedanceAdapter,
                GenerationProvider.MOCK_IMAGE: MockImageAdapter,
            }[provider]

            registry.register(
                config=GenerationConfig(
                    provider=provider,
                    model_name=item["model_name"],
                    endpoint=item.get("endpoint"),
                    api_key=item.get("api_key"),
                    timeout_seconds=float(item.get("timeout_seconds", 120.0)),
                    max_retries=int(item.get("max_retries", 1)),
                    capabilities=capabilities,
                    default_headers=item.get("default_headers", {}),
                    default_params=item.get("default_params", {}),
                    enabled=bool(item.get("enabled", True)),
                    metadata=item.get("metadata", {}),
                ),
                adapter_cls=adapter_cls,
                aliases=item.get("aliases", []),
                is_default=bool(item.get("is_default", False)),
            )
        return registry

    seedance_endpoint = os.getenv("AI_PAAS_SEEDANCE_ENDPOINT")
    seedance_api_key = os.getenv("AI_PAAS_SEEDANCE_API_KEY")
    seedance_model = os.getenv("AI_PAAS_SEEDANCE_MODEL", "seedance-v1")
    if seedance_endpoint and seedance_api_key:
        registry.register(
            config=GenerationConfig(
                provider=GenerationProvider.SEEDANCE,
                model_name=seedance_model,
                endpoint=seedance_endpoint,
                api_key=seedance_api_key,
                capabilities=frozenset({GenerationCapability.VIDEO}),
                enabled=True,
                metadata={"source": "default_env"},
            ),
            adapter_cls=SeedanceAdapter,
            aliases=["seedance-default", "video-default"],
            is_default=True,
        )

    enable_mock_image = os.getenv("AI_PAAS_ENABLE_MOCK_IMAGE_PROVIDER", "false").lower() == "true"
    if enable_mock_image:
        registry.register(
            config=GenerationConfig(
                provider=GenerationProvider.MOCK_IMAGE,
                model_name=os.getenv("AI_PAAS_MOCK_IMAGE_MODEL", "mock-image-v1"),
                capabilities=frozenset({GenerationCapability.IMAGE}),
                enabled=True,
                metadata={"source": "default_env"},
            ),
            adapter_cls=MockImageAdapter,
            aliases=["mock-image-default", "image-default"],
            is_default=True,
        )

    return registry


def build_generation_service(
    *,
    config: Optional[Dict[str, Any]] = None,
    trace_store: Optional[Any] = None,
    runtime_metrics: Optional[Any] = None,
) -> GenerationService:
    registry = build_generation_registry(config=config)
    return GenerationService(
        registry=registry,
        trace_store=trace_store,
        runtime_metrics=runtime_metrics,
    )


def build_generation_toolset(
    *,
    config: Optional[Dict[str, Any]] = None,
    trace_store: Optional[Any] = None,
    runtime_metrics: Optional[Any] = None,
) -> GenerationToolSet:
    service = build_generation_service(
        config=config,
        trace_store=trace_store,
        runtime_metrics=runtime_metrics,
    )
    return GenerationToolSet(
        generation_service=service,
        default_image_model_ref=os.getenv("AI_PAAS_DEFAULT_IMAGE_MODEL_REF"),
        default_video_model_ref=os.getenv("AI_PAAS_DEFAULT_VIDEO_MODEL_REF"),
    )