from __future__ import annotations

from typing import Any, Dict, Optional

from runtime.llm_adapter import BaseLLMAdapter
from runtime.model_backed_llm_adapter import ModelBackedLLMAdapter
from runtime.model_service import ModelService
from runtime.models.defaults import register_default_models, register_model_definitions
from runtime.models.model_registry import ModelRegistry


def build_model_registry(
    config: Optional[Dict[str, Any]] = None,
) -> ModelRegistry:
    registry = ModelRegistry()
    config = config or {}

    model_definitions = config.get("models", [])
    if model_definitions:
        register_model_definitions(registry=registry, definitions=model_definitions)
    else:
        register_default_models(registry=registry)

    return registry


def build_model_service(
    *,
    config: Optional[Dict[str, Any]] = None,
    trace_store: Optional[Any] = None,
    runtime_metrics: Optional[Any] = None,
) -> ModelService:
    registry = build_model_registry(config=config)
    return ModelService(
        registry=registry,
        trace_store=trace_store,
        runtime_metrics=runtime_metrics,
    )


def build_model_backed_llm_adapter(
    *,
    config: Optional[Dict[str, Any]] = None,
    trace_store: Optional[Any] = None,
    runtime_metrics: Optional[Any] = None,
    default_model_ref: Optional[str] = None,
) -> BaseLLMAdapter:
    model_service = build_model_service(
        config=config,
        trace_store=trace_store,
        runtime_metrics=runtime_metrics,
    )
    return ModelBackedLLMAdapter(
        model_service=model_service,
        default_model_ref=default_model_ref,
    )