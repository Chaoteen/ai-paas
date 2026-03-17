from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from runtime.models.exceptions import ModelRegistryError
from runtime.models.model_registry import ModelRegistry
from runtime.models.types import ModelCapability, ModelConfig, ModelProvider


@dataclass(frozen=True)
class ModelSelectionInput:
    model_ref: Optional[str] = None
    provider: Optional[ModelProvider] = None
    requires: frozenset[ModelCapability] = frozenset()


class ModelSelector:
    """
    Model selection policy.

    Order:
    1. explicit model_ref
    2. provider + requires
    3. provider default
    4. alias 'default'
    5. any enabled model matching requires
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

        try:
            return self._registry.resolve_config("default")
        except ModelRegistryError:
            if request.requires:
                return self._registry.find_first_by_capabilities(
                    provider=None,
                    requires=set(request.requires),
                )
            raise