from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Type

from runtime.models.base import BaseModelAdapter
from runtime.models.exceptions import ModelRegistryError
from runtime.models.types import (
    ModelCapability,
    ModelConfig,
    ModelProvider,
    RegistryFilter,
)


@dataclass(frozen=True)
class RegisteredModel:
    config: ModelConfig
    adapter_cls: Type[BaseModelAdapter]


class ModelRegistry:
    """
    Registry for model configs + adapter implementations.

    Responsibilities:
    - register model definitions
    - resolve by exact key / alias / provider+name
    - instantiate provider adapters
    - list models by capabilities
    """

    def __init__(self) -> None:
        self._models: Dict[str, RegisteredModel] = {}
        self._aliases: Dict[str, str] = {}
        self._default_keys: Dict[ModelProvider, str] = {}

    def register(
        self,
        config: ModelConfig,
        adapter_cls: Type[BaseModelAdapter],
        aliases: Optional[List[str]] = None,
        is_default: bool = False,
    ) -> None:
        key = config.registry_key
        if key in self._models:
            raise ModelRegistryError(f"model already registered: {key}")

        self._models[key] = RegisteredModel(config=config, adapter_cls=adapter_cls)

        for alias in aliases or []:
            normalized = self._normalize_alias(alias)
            if normalized in self._aliases:
                raise ModelRegistryError(f"alias already registered: {alias}")
            self._aliases[normalized] = key

        provider_name_key = f"{config.provider.value}:{config.model_name}"
        if provider_name_key not in self._aliases:
            self._aliases[provider_name_key] = key

        bare_name_key = self._normalize_alias(config.model_name)
        if bare_name_key not in self._aliases:
            self._aliases[bare_name_key] = key

        if is_default:
            self._default_keys[config.provider] = key

    def resolve_config(self, model_ref: str) -> ModelConfig:
        return self._resolve_registered(model_ref).config

    def create_adapter(self, model_ref: str) -> BaseModelAdapter:
        registered = self._resolve_registered(model_ref)
        return registered.adapter_cls(registered.config)

    def get_default(self, provider: ModelProvider) -> ModelConfig:
        if provider not in self._default_keys:
            raise ModelRegistryError(f"no default model configured for provider: {provider.value}")
        return self._models[self._default_keys[provider]].config

    def create_default_adapter(self, provider: ModelProvider) -> BaseModelAdapter:
        if provider not in self._default_keys:
            raise ModelRegistryError(f"no default model configured for provider: {provider.value}")
        key = self._default_keys[provider]
        registered = self._models[key]
        return registered.adapter_cls(registered.config)

    def list_models(self, filter_by: Optional[RegistryFilter] = None) -> List[ModelConfig]:
        filter_by = filter_by or RegistryFilter()
        results: List[ModelConfig] = []

        for registered in self._models.values():
            config = registered.config

            if filter_by.enabled_only and not config.enabled:
                continue

            if filter_by.provider and config.provider != filter_by.provider:
                continue

            if filter_by.requires and not filter_by.requires.issubset(config.capabilities):
                continue

            results.append(config)

        results.sort(key=lambda c: (c.provider.value, c.model_name, c.version or ""))
        return results

    def find_first_by_capabilities(
        self,
        provider: Optional[ModelProvider] = None,
        requires: Optional[set[ModelCapability]] = None,
    ) -> ModelConfig:
        requires = requires or set()
        filter_by = RegistryFilter(
            provider=provider,
            requires=frozenset(requires),
            enabled_only=True,
        )
        models = self.list_models(filter_by=filter_by)
        if not models:
            provider_str = provider.value if provider else "any"
            req_str = ",".join(sorted(cap.value for cap in requires)) if requires else "none"
            raise ModelRegistryError(
                f"no model found for provider={provider_str} capabilities={req_str}"
            )
        return models[0]

    def _resolve_registered(self, model_ref: str) -> RegisteredModel:
        normalized = self._normalize_alias(model_ref)

        if normalized in self._models:
            return self._models[normalized]

        if normalized in self._aliases:
            return self._models[self._aliases[normalized]]

        raise ModelRegistryError(f"model not found: {model_ref}")

    @staticmethod
    def _normalize_alias(alias: str) -> str:
        return alias.strip().lower()