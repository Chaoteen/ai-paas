from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from runtime.models.exceptions import ModelRegistryError
from runtime.models.model_registry import ModelRegistry
from runtime.models.routing_policy import get_routing_policy
from runtime.models.types import ModelCapability, ModelConfig, ModelProvider, RegistryFilter


@dataclass(frozen=True)
class ModelSelectionInput:
    model_ref: Optional[str] = None
    provider: Optional[ModelProvider] = None
    requires: frozenset[ModelCapability] = frozenset()
    routing_policy: Optional[str] = None


class ModelSelector:
    """
    Model selection policy.

    Order:
    1. explicit model_ref
    2. explicit provider + requires
    3. explicit provider default
    4. routing_policy ordered selection
    5. alias 'default'
    6. any enabled model matching requires
    """

    def __init__(self, registry: ModelRegistry) -> None:
        self._registry = registry

    def select(self, request: ModelSelectionInput) -> ModelConfig:
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
        except ModelRegistryError:
            if request.requires:
                return self._registry.find_first_by_capabilities(
                    provider=None,
                    requires=set(request.requires),
                )
            raise

    def _select_by_routing_policy(self, request: ModelSelectionInput) -> Optional[ModelConfig]:
        policy = get_routing_policy(request.routing_policy)

        for provider in policy.provider_order:
            models = self._registry.list_models(
                filter_by=RegistryFilter(
                    provider=provider,
                    requires=request.requires,
                    enabled_only=True,
                )
            )
            if models:
                return models[0]

        if policy.fallback_to_any:
            models = self._registry.list_models(
                filter_by=RegistryFilter(
                    provider=None,
                    requires=request.requires,
                    enabled_only=True,
                )
            )
            if models:
                return models[0]

        return None