from __future__ import annotations

import os
from typing import List

from runtime.models.adapters.deepseek_adapter import DeepSeekAdapter
from runtime.models.adapters.doubao_adapter import DoubaoAdapter
from runtime.models.adapters.kimi_adapter import KimiAdapter
from runtime.models.adapters.minimax_adapter import MiniMaxAdapter
from runtime.models.adapters.ollama_adapter import OllamaAdapter
from runtime.models.adapters.openai_adapter import OpenAIAdapter
from runtime.models.adapters.qwen_adapter import QwenAdapter
from runtime.models.model_registry import ModelRegistry
from runtime.models.types import ModelCapability, ModelConfig, ModelProvider


def register_default_models(registry: ModelRegistry) -> None:
    """
    Register a conservative default set of models for local/dev usage.

    Runtime field alignment rule:
    - registry stores provider/model capability metadata only
    - task/tenant/workflow/correlation fields stay in ExecutionContext
    """

    ollama_endpoint = os.getenv(
        "AI_PAAS_OLLAMA_ENDPOINT",
        "http://127.0.0.1:11434/v1/chat/completions",
    )
    ollama_model = os.getenv("AI_PAAS_OLLAMA_MODEL", "qwen3:14b")
    ollama_tools = os.getenv("AI_PAAS_OLLAMA_TOOLS", "false").lower() == "true"

    ollama_capabilities = {ModelCapability.CHAT, ModelCapability.STREAMING}
    if ollama_tools:
        ollama_capabilities.add(ModelCapability.TOOLS)

    registry.register(
        config=ModelConfig(
            provider=ModelProvider.OLLAMA,
            model_name=ollama_model,
            endpoint=ollama_endpoint,
            capabilities=frozenset(ollama_capabilities),
            enabled=True,
            metadata={"source": "default_env"},
        ),
        adapter_cls=OllamaAdapter,
        aliases=["default", "local-default", "ollama-default"],
        is_default=True,
    )

    _register_openai_family_provider_from_env(
        registry=registry,
        provider=ModelProvider.OPENAI,
        adapter_cls=OpenAIAdapter,
        endpoint_env="AI_PAAS_OPENAI_ENDPOINT",
        model_env="AI_PAAS_OPENAI_MODEL",
        api_key_env="AI_PAAS_OPENAI_API_KEY",
        default_model="gpt-4o-mini",
        aliases=["openai-default"],
    )

    _register_openai_family_provider_from_env(
        registry=registry,
        provider=ModelProvider.QWEN,
        adapter_cls=QwenAdapter,
        endpoint_env="AI_PAAS_QWEN_ENDPOINT",
        model_env="AI_PAAS_QWEN_MODEL",
        api_key_env="AI_PAAS_QWEN_API_KEY",
        default_model="qwen-max",
        aliases=["qwen-default"],
    )

    _register_openai_family_provider_from_env(
        registry=registry,
        provider=ModelProvider.DEEPSEEK,
        adapter_cls=DeepSeekAdapter,
        endpoint_env="AI_PAAS_DEEPSEEK_ENDPOINT",
        model_env="AI_PAAS_DEEPSEEK_MODEL",
        api_key_env="AI_PAAS_DEEPSEEK_API_KEY",
        default_model="deepseek-chat",
        aliases=["deepseek-default"],
    )

    _register_openai_family_provider_from_env(
        registry=registry,
        provider=ModelProvider.KIMI,
        adapter_cls=KimiAdapter,
        endpoint_env="AI_PAAS_KIMI_ENDPOINT",
        model_env="AI_PAAS_KIMI_MODEL",
        api_key_env="AI_PAAS_KIMI_API_KEY",
        default_model="kimi-k2.5",
        aliases=["kimi-default"],
    )

    _register_openai_family_provider_from_env(
        registry=registry,
        provider=ModelProvider.MINIMAX,
        adapter_cls=MiniMaxAdapter,
        endpoint_env="AI_PAAS_MINIMAX_ENDPOINT",
        model_env="AI_PAAS_MINIMAX_MODEL",
        api_key_env="AI_PAAS_MINIMAX_API_KEY",
        default_model="MiniMax-M2.5",
        aliases=["minimax-default"],
    )

    _register_openai_family_provider_from_env(
        registry=registry,
        provider=ModelProvider.DOUBAO,
        adapter_cls=DoubaoAdapter,
        endpoint_env="AI_PAAS_DOUBAO_ENDPOINT",
        model_env="AI_PAAS_DOUBAO_MODEL",
        api_key_env="AI_PAAS_DOUBAO_API_KEY",
        default_model="doubao-seed-1-6",
        aliases=["doubao-default"],
    )


def _register_openai_family_provider_from_env(
    *,
    registry: ModelRegistry,
    provider: ModelProvider,
    adapter_cls,
    endpoint_env: str,
    model_env: str,
    api_key_env: str,
    default_model: str,
    aliases: list[str],
) -> None:
    endpoint = os.getenv(endpoint_env)
    model_name = os.getenv(model_env, default_model)
    api_key = os.getenv(api_key_env)

    if endpoint and api_key:
        registry.register(
            config=ModelConfig(
                provider=provider,
                model_name=model_name,
                endpoint=endpoint,
                api_key=api_key,
                capabilities=frozenset(
                    {
                        ModelCapability.CHAT,
                        ModelCapability.TOOLS,
                        ModelCapability.JSON_MODE,
                        ModelCapability.STREAMING,
                    }
                ),
                enabled=True,
                metadata={"source": "default_env"},
            ),
            adapter_cls=adapter_cls,
            aliases=aliases,
            is_default=True,
        )


def register_model_definitions(
    registry: ModelRegistry,
    definitions: List[dict],
) -> None:
    provider_to_adapter = {
        ModelProvider.OLLAMA: OllamaAdapter,
        ModelProvider.OPENAI: OpenAIAdapter,
        ModelProvider.QWEN: QwenAdapter,
        ModelProvider.DEEPSEEK: DeepSeekAdapter,
        ModelProvider.KIMI: KimiAdapter,
        ModelProvider.MINIMAX: MiniMaxAdapter,
        ModelProvider.DOUBAO: DoubaoAdapter,
    }

    for item in definitions:
        provider = ModelProvider(item["provider"])
        capabilities = frozenset(
            ModelCapability(value) for value in item.get("capabilities", [])
        )

        config = ModelConfig(
            provider=provider,
            model_name=item["model_name"],
            endpoint=item.get("endpoint"),
            api_key=item.get("api_key"),
            organization=item.get("organization"),
            timeout_seconds=float(item.get("timeout_seconds", 60.0)),
            max_retries=int(item.get("max_retries", 1)),
            capabilities=capabilities,
            default_headers=item.get("default_headers", {}),
            default_params=item.get("default_params", {}),
            enabled=bool(item.get("enabled", True)),
            metadata=item.get("metadata", {}),
            version=item.get("version"),
            display_name=item.get("display_name"),
        )

        registry.register(
            config=config,
            adapter_cls=provider_to_adapter[provider],
            aliases=item.get("aliases", []),
            is_default=bool(item.get("is_default", False)),
        )