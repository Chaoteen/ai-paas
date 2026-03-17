from __future__ import annotations

import os
from typing import List

from runtime.models.adapters.deepseek_adapter import DeepSeekAdapter
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

    openai_endpoint = os.getenv("AI_PAAS_OPENAI_ENDPOINT")
    openai_model = os.getenv("AI_PAAS_OPENAI_MODEL", "gpt-4o-mini")
    openai_api_key = os.getenv("AI_PAAS_OPENAI_API_KEY")
    if openai_endpoint and openai_api_key:
        registry.register(
            config=ModelConfig(
                provider=ModelProvider.OPENAI,
                model_name=openai_model,
                endpoint=openai_endpoint,
                api_key=openai_api_key,
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
            adapter_cls=OpenAIAdapter,
            aliases=["openai-default"],
            is_default=True,
        )

    qwen_endpoint = os.getenv("AI_PAAS_QWEN_ENDPOINT")
    qwen_model = os.getenv("AI_PAAS_QWEN_MODEL", "qwen-max")
    qwen_api_key = os.getenv("AI_PAAS_QWEN_API_KEY")
    if qwen_endpoint and qwen_api_key:
        registry.register(
            config=ModelConfig(
                provider=ModelProvider.QWEN,
                model_name=qwen_model,
                endpoint=qwen_endpoint,
                api_key=qwen_api_key,
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
            adapter_cls=QwenAdapter,
            aliases=["qwen-default"],
            is_default=True,
        )

    deepseek_endpoint = os.getenv("AI_PAAS_DEEPSEEK_ENDPOINT")
    deepseek_model = os.getenv("AI_PAAS_DEEPSEEK_MODEL", "deepseek-chat")
    deepseek_api_key = os.getenv("AI_PAAS_DEEPSEEK_API_KEY")
    if deepseek_endpoint and deepseek_api_key:
        registry.register(
            config=ModelConfig(
                provider=ModelProvider.DEEPSEEK,
                model_name=deepseek_model,
                endpoint=deepseek_endpoint,
                api_key=deepseek_api_key,
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
            adapter_cls=DeepSeekAdapter,
            aliases=["deepseek-default"],
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