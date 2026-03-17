from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from runtime.models.types import ModelProvider


class RoutingPolicyName:
    BALANCED = "balanced"
    LOCAL_FIRST = "local_first"
    CLOUD_FIRST = "cloud_first"
    COST_OPTIMIZED = "cost_optimized"
    RELIABILITY_FIRST = "reliability_first"


@dataclass(frozen=True)
class ModelRoutingPolicy:
    name: str
    provider_order: List[ModelProvider]
    fallback_to_any: bool = True


def get_routing_policy(name: Optional[str]) -> ModelRoutingPolicy:
    normalized = (name or RoutingPolicyName.BALANCED).strip().lower()

    if normalized == RoutingPolicyName.LOCAL_FIRST:
        return ModelRoutingPolicy(
            name=RoutingPolicyName.LOCAL_FIRST,
            provider_order=[
                ModelProvider.OLLAMA,
                ModelProvider.DEEPSEEK,
                ModelProvider.QWEN,
                ModelProvider.OPENAI,
            ],
            fallback_to_any=True,
        )

    if normalized == RoutingPolicyName.CLOUD_FIRST:
        return ModelRoutingPolicy(
            name=RoutingPolicyName.CLOUD_FIRST,
            provider_order=[
                ModelProvider.OPENAI,
                ModelProvider.QWEN,
                ModelProvider.DEEPSEEK,
                ModelProvider.OLLAMA,
            ],
            fallback_to_any=True,
        )

    if normalized == RoutingPolicyName.COST_OPTIMIZED:
        return ModelRoutingPolicy(
            name=RoutingPolicyName.COST_OPTIMIZED,
            provider_order=[
                ModelProvider.OLLAMA,
                ModelProvider.DEEPSEEK,
                ModelProvider.QWEN,
                ModelProvider.OPENAI,
            ],
            fallback_to_any=True,
        )

    if normalized == RoutingPolicyName.RELIABILITY_FIRST:
        return ModelRoutingPolicy(
            name=RoutingPolicyName.RELIABILITY_FIRST,
            provider_order=[
                ModelProvider.OPENAI,
                ModelProvider.QWEN,
                ModelProvider.DEEPSEEK,
                ModelProvider.OLLAMA,
            ],
            fallback_to_any=True,
        )

    return ModelRoutingPolicy(
        name=RoutingPolicyName.BALANCED,
        provider_order=[
            ModelProvider.OLLAMA,
            ModelProvider.OPENAI,
            ModelProvider.QWEN,
            ModelProvider.DEEPSEEK,
        ],
        fallback_to_any=True,
    )