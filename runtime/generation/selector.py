from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from runtime.generation.exceptions import GenerationRegistryError
from runtime.generation.generation_registry import GenerationRegistry
from runtime.generation.routing_policy import get_generation_routing_policy
from runtime.generation.types import (
    GenerationCapability,
    GenerationConfig,
    GenerationProvider,
    GenerationRegistryFilter,
)


@dataclass(frozen=True)
class GenerationSelectionInput:
    model_ref: Optional[str] = None
    provider: Optional[GenerationProvider] = None
    requires: frozenset[GenerationCapability] = frozenset()
    routing_policy: Optional[str] = None


class GenerationSelector:
    def __init__(self, registry: GenerationRegistry) -> None:
        self._registry = registry

    def select(self, request: GenerationSelectionInput) -> GenerationConfig:
        if request.model_ref:
            return self._registry.resolve_config(request.model_ref)

        if request.provider and request.requires:
            return self._registry.find_first_by_capabilities(
                provider=request.provider,
                requires=set(request.requires),
            )

        if request.provider:
            return self._registry.get_default(request.provider)

        selected = self._select_by_routing_policy(request)
        if selected is not None:
            return selected

        try:
            return self._registry.resolve_config("default")
        except GenerationRegistryError:
            if request.requires:
                return self._registry.find_first_by_capabilities(
                    provider=None,
                    requires=set(request.requires),
                )
            raise

    def _select_by_routing_policy(
        self,
        request: GenerationSelectionInput,
    ) -> Optional[GenerationConfig]:
        policy = get_generation_routing_policy(request.routing_policy)

        for provider in policy.provider_order:
            models = self._registry.list_models(
                filter_by=GenerationRegistryFilter(
                    provider=provider,
                    requires=request.requires,
                    enabled_only=True,
                )
            )
            if models:
                return models[0]

        if policy.fallback_to_any:
            models = self._registry.list_models(
                filter_by=GenerationRegistryFilter(
                    provider=None,
                    requires=request.requires,
                    enabled_only=True,
                )
            )
            if models:
                return models[0]

        return None