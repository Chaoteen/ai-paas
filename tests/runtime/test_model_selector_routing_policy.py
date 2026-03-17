from __future__ import annotations

from runtime.models.adapters.deepseek_adapter import DeepSeekAdapter
from runtime.models.adapters.ollama_adapter import OllamaAdapter
from runtime.models.adapters.openai_adapter import OpenAIAdapter
from runtime.models.model_registry import ModelRegistry
from runtime.models.selector import ModelSelectionInput, ModelSelector
from runtime.models.types import ModelCapability, ModelConfig, ModelProvider


def _build_registry() -> ModelRegistry:
    registry = ModelRegistry()

    registry.register(
        config=ModelConfig(
            provider=ModelProvider.OLLAMA,
            model_name="local-chat",
            endpoint="http://127.0.0.1:11434/v1/chat/completions",
            capabilities=frozenset({ModelCapability.CHAT}),
        ),
        adapter_cls=OllamaAdapter,
        aliases=["ollama-local"],
        is_default=True,
    )

    registry.register(
        config=ModelConfig(
            provider=ModelProvider.OPENAI,
            model_name="gpt-4o-mini",
            endpoint="https://api.openai.com/v1/chat/completions",
            api_key="test-key",
            capabilities=frozenset({ModelCapability.CHAT, ModelCapability.TOOLS}),
        ),
        adapter_cls=OpenAIAdapter,
        aliases=["openai-main"],
        is_default=True,
    )

    registry.register(
        config=ModelConfig(
            provider=ModelProvider.DEEPSEEK,
            model_name="deepseek-chat",
            endpoint="https://api.deepseek.com/chat/completions",
            api_key="test-key",
            capabilities=frozenset({ModelCapability.CHAT, ModelCapability.TOOLS}),
        ),
        adapter_cls=DeepSeekAdapter,
        aliases=["deepseek-main"],
        is_default=True,
    )

    return registry


def test_selector_local_first_prefers_ollama() -> None:
    selector = ModelSelector(_build_registry())
    selected = selector.select(
        ModelSelectionInput(
            requires=frozenset({ModelCapability.CHAT}),
            routing_policy="local_first",
        )
    )
    assert selected.provider == ModelProvider.OLLAMA
    assert selected.model_name == "local-chat"


def test_selector_cloud_first_prefers_openai() -> None:
    selector = ModelSelector(_build_registry())
    selected = selector.select(
        ModelSelectionInput(
            requires=frozenset({ModelCapability.CHAT, ModelCapability.TOOLS}),
            routing_policy="cloud_first",
        )
    )
    assert selected.provider == ModelProvider.OPENAI
    assert selected.model_name == "gpt-4o-mini"


def test_selector_cost_optimized_prefers_ollama_when_capability_matches() -> None:
    selector = ModelSelector(_build_registry())
    selected = selector.select(
        ModelSelectionInput(
            requires=frozenset({ModelCapability.CHAT}),
            routing_policy="cost_optimized",
        )
    )
    assert selected.provider == ModelProvider.OLLAMA


def test_selector_falls_back_when_first_provider_cannot_satisfy_requires() -> None:
    selector = ModelSelector(_build_registry())
    selected = selector.select(
        ModelSelectionInput(
            requires=frozenset({ModelCapability.CHAT, ModelCapability.TOOLS}),
            routing_policy="cost_optimized",
        )
    )
    assert selected.provider in {ModelProvider.DEEPSEEK, ModelProvider.OPENAI}