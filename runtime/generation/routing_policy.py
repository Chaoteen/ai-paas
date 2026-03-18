from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from runtime.generation.types import GenerationProvider


class GenerationRoutingPolicyName:
    BALANCED = "balanced"
    VIDEO_FIRST = "video_first"
    IMAGE_FIRST = "image_first"


@dataclass(frozen=True)
class GenerationRoutingPolicy:
    name: str
    provider_order: List[GenerationProvider]
    fallback_to_any: bool = True


def get_generation_routing_policy(name: Optional[str]) -> GenerationRoutingPolicy:
    normalized = (name or GenerationRoutingPolicyName.BALANCED).strip().lower()

    if normalized == GenerationRoutingPolicyName.VIDEO_FIRST:
        return GenerationRoutingPolicy(
            name=GenerationRoutingPolicyName.VIDEO_FIRST,
            provider_order=[
                GenerationProvider.SEEDANCE,
                GenerationProvider.MOCK_IMAGE,
            ],
            fallback_to_any=True,
        )

    if normalized == GenerationRoutingPolicyName.IMAGE_FIRST:
        return GenerationRoutingPolicy(
            name=GenerationRoutingPolicyName.IMAGE_FIRST,
            provider_order=[
                GenerationProvider.MOCK_IMAGE,
                GenerationProvider.SEEDANCE,
            ],
            fallback_to_any=True,
        )

    return GenerationRoutingPolicy(
        name=GenerationRoutingPolicyName.BALANCED,
        provider_order=[
            GenerationProvider.SEEDANCE,
            GenerationProvider.MOCK_IMAGE,
        ],
        fallback_to_any=True,
    )