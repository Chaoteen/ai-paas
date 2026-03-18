from __future__ import annotations

from runtime.models.adapters.doubao_adapter import DoubaoAdapter
from runtime.models.adapters.kimi_adapter import KimiAdapter
from runtime.models.adapters.minimax_adapter import MiniMaxAdapter
from runtime.models.model_registry import ModelRegistry
from runtime.models.types import ModelCapability, ModelConfig, ModelProvider


def test_registry_registers_kimi_minimax_doubao() -> None:
    registry = ModelRegistry()

    registry.register(
        config=ModelConfig(
            provider=ModelProvider.KIMI,
            model_name="kimi-k2.5",
            endpoint="https://kimi.example.com/v1/chat/completions",
            api_key="kimi-key",
            capabilities=frozenset({ModelCapability.CHAT, ModelCapability.TOOLS}),
        ),
        adapter_cls=KimiAdapter,
        aliases=["kimi-default"],
        is_default=True,
    )

    registry.register(
        config=ModelConfig(
            provider=ModelProvider.MINIMAX,
            model_name="MiniMax-M2.5",
            endpoint="https://minimax.example.com/v1/chat/completions",
            api_key="minimax-key",
            capabilities=frozenset({ModelCapability.CHAT, ModelCapability.TOOLS}),
        ),
        adapter_cls=MiniMaxAdapter,
        aliases=["minimax-default"],
        is_default=True,
    )

    registry.register(
        config=ModelConfig(
            provider=ModelProvider.DOUBAO,
            model_name="doubao-seed-1-6",
            endpoint="https://volc.example.com/v1/chat/completions",
            api_key="doubao-key",
            capabilities=frozenset({ModelCapability.CHAT, ModelCapability.TOOLS}),
        ),
        adapter_cls=DoubaoAdapter,
        aliases=["doubao-default"],
        is_default=True,
    )

    kimi = registry.resolve_config("kimi-default")
    minimax = registry.resolve_config("minimax-default")
    doubao = registry.resolve_config("doubao-default")

    assert kimi.provider == ModelProvider.KIMI
    assert minimax.provider == ModelProvider.MINIMAX
    assert doubao.provider == ModelProvider.DOUBAO