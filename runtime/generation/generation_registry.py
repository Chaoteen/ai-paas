from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Type

from runtime.generation.base import BaseGenerationAdapter
from runtime.generation.exceptions import GenerationRegistryError
from runtime.generation.types import (
    GenerationCapability,
    GenerationConfig,
    GenerationProvider,
    GenerationRegistryFilter,
)


@dataclass(frozen=True)
class RegisteredGenerationModel:
    config: GenerationConfig
    adapter_cls: Type[BaseGenerationAdapter]


class GenerationRegistry:
    def __init__(self) -> None:
        self._models: Dict[str, RegisteredGenerationModel] = {}
        self._aliases: Dict[str, str] = {}
        self._default_keys: Dict[GenerationProvider, str] = {}

    def register(
        self,
        *,
        config: GenerationConfig,
        adapter_cls: Type[BaseGenerationAdapter],
        aliases: Optional[List[str]] = None,
        is_default: bool = False,
    ) -> None:
        key = config.registry_key
        if key in self._models:
            raise GenerationRegistryError(f"generation model already registered: {key}")

        self._models[key] = RegisteredGenerationModel(config=config, adapter_cls=adapter_cls)

        for alias in aliases or []:
            normalized = self._normalize(alias)
            if normalized in self._aliases:
                raise GenerationRegistryError(f"alias already registered: {alias}")
            self._aliases[normalized] = key

        provider_name_key = f"{config.provider.value}:{config.model_name}"
        if provider_name_key not in self._aliases:
            self._aliases[provider_name_key] = key

        if is_default:
            self._default_keys[config.provider] = key

    def resolve_config(self, ref: str) -> GenerationConfig:
        return self._resolve_registered(ref).config

    def create_adapter(self, ref: str) -> BaseGenerationAdapter:
        registered = self._resolve_registered(ref)
        return registered.adapter_cls(registered.config)

    def get_default(self, provider: GenerationProvider) -> GenerationConfig:
        if provider not in self._default_keys:
            raise GenerationRegistryError(f"no default generation model for provider: {provider.value}")
        return self._models[self._default_keys[provider]].config

    def list_models(
        self,
        *,
        filter_by: Optional[GenerationRegistryFilter] = None,
    ) -> List[GenerationConfig]:
        filter_by = filter_by or GenerationRegistryFilter()
        results: list[GenerationConfig] = []

        for item in self._models.values():
            config = item.config

            if filter_by.enabled_only and not config.enabled:
                continue
            if filter_by.provider and config.provider != filter_by.provider:
                continue
            if filter_by.requires and not filter_by.requires.issubset(config.capabilities):
                continue

            results.append(config)

        results.sort(key=lambda c: (c.provider.value, c.model_name))
        return results

    def find_first_by_capabilities(
        self,
        *,
        provider: Optional[GenerationProvider] = None,
        requires: Optional[set[GenerationCapability]] = None,
    ) -> GenerationConfig:
        requires = requires or set()
        models = self.list_models(
            filter_by=GenerationRegistryFilter(
                provider=provider,
                requires=frozenset(requires),
                enabled_only=True,
            )
        )
        if not models:
            raise GenerationRegistryError(
                f"no generation model found for provider={provider.value if provider else 'any'} "
                f"capabilities={','.join(sorted(x.value for x in requires)) if requires else 'none'}"
            )
        return models[0]

    def _resolve_registered(self, ref: str) -> RegisteredGenerationModel:
        normalized = self._normalize(ref)
        if normalized in self._models:
            return self._models[normalized]
        if normalized in self._aliases:
            return self._models[self._aliases[normalized]]
        raise GenerationRegistryError(f"generation model not found: {ref}")

    @staticmethod
    def _normalize(value: str) -> str:
        return value.strip().lower()