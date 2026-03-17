from __future__ import annotations

import pytest

from runtime.models.adapters.deepseek_adapter import DeepSeekAdapter
from runtime.models.adapters.ollama_adapter import OllamaAdapter
from runtime.models.adapters.openai_adapter import OpenAIAdapter
from runtime.models.exceptions import ModelRegistryError
from runtime.models.model_registry import ModelRegistry
from runtime.models.types import ModelCapability, ModelConfig, ModelProvider


def test_model_registry_register_and_resolve_by_alias() -> None:
    registry = ModelRegistry()

    config = ModelConfig(
        provider=ModelProvider.OLLAMA,
        model_name="qwen3:14b",
        endpoint="http://127.0.0.1:11434/v1/chat/completions",
        capabilities=frozenset({ModelCapability.CHAT, ModelCapability.STREAMING}),
    )

    registry.register(
        config=config,
        adapter_cls=OllamaAdapter,
        aliases=["local-main", "default-ollama"],
        is_default=True,
    )

    resolved = registry.resolve_config("local-main")
    assert resolved.model_name == "qwen3:14b"
    assert resolved.provider == ModelProvider.OLLAMA

    default_cfg = registry.get_default(ModelProvider.OLLAMA)
    assert default_cfg.model_name == "qwen3:14b"


def test_model_registry_create_adapter() -> None:
    registry = ModelRegistry()

    config = ModelConfig(
        provider=ModelProvider.OPENAI,
        model_name="gpt-4o-mini",
        endpoint="https://api.openai.com/v1/chat/completions",
        api_key="test-key",
        capabilities=frozenset({ModelCapability.CHAT, ModelCapability.TOOLS}),
    )

    registry.register(config=config, adapter_cls=OpenAIAdapter, aliases=["openai-main"])
    adapter = registry.create_adapter("openai-main")

    assert isinstance(adapter, OpenAIAdapter)
    assert adapter.config.model_name == "gpt-4o-mini"


def test_model_registry_find_first_by_capabilities() -> None:
    registry = ModelRegistry()

    registry.register(
        config=ModelConfig(
            provider=ModelProvider.OLLAMA,
            model_name="local-basic",
            endpoint="http://127.0.0.1:11434/v1/chat/completions",
            capabilities=frozenset({ModelCapability.CHAT}),
        ),
        adapter_cls=OllamaAdapter,
    )
    registry.register(
        config=ModelConfig(
            provider=ModelProvider.DEEPSEEK,
            model_name="deepseek-chat",
            endpoint="https://api.deepseek.com/chat/completions",
            api_key="deepseek-key",
            capabilities=frozenset({ModelCapability.CHAT, ModelCapability.TOOLS}),
        ),
        adapter_cls=DeepSeekAdapter,
    )

    found = registry.find_first_by_capabilities(
        requires={ModelCapability.CHAT, ModelCapability.TOOLS}
    )
    assert found.provider == ModelProvider.DEEPSEEK
    assert found.model_name == "deepseek-chat"


def test_model_registry_duplicate_alias_raises() -> None:
    registry = ModelRegistry()

    registry.register(
        config=ModelConfig(
            provider=ModelProvider.OPENAI,
            model_name="gpt-4o-mini",
            endpoint="https://api.openai.com/v1/chat/completions",
            api_key="k1",
            capabilities=frozenset({ModelCapability.CHAT}),
        ),
        adapter_cls=OpenAIAdapter,
        aliases=["shared-alias"],
    )

    with pytest.raises(ModelRegistryError):
        registry.register(
            config=ModelConfig(
                provider=ModelProvider.OPENAI,
                model_name="gpt-4.1-mini",
                endpoint="https://api.openai.com/v1/chat/completions",
                api_key="k2",
                capabilities=frozenset({ModelCapability.CHAT}),
            ),
            adapter_cls=OpenAIAdapter,
            aliases=["shared-alias"],
        )


def test_model_registry_missing_model_raises() -> None:
    registry = ModelRegistry()
    with pytest.raises(ModelRegistryError):
        registry.resolve_config("missing-model")