from __future__ import annotations

from runtime.models.routing_policy import (
    RoutingPolicyName,
    get_routing_policy,
)
from runtime.models.types import ModelProvider


def test_get_routing_policy_local_first() -> None:
    policy = get_routing_policy("local_first")
    assert policy.name == RoutingPolicyName.LOCAL_FIRST
    assert policy.provider_order[0] == ModelProvider.OLLAMA


def test_get_routing_policy_cloud_first() -> None:
    policy = get_routing_policy("cloud_first")
    assert policy.name == RoutingPolicyName.CLOUD_FIRST
    assert policy.provider_order[0] == ModelProvider.OPENAI


def test_get_routing_policy_cost_optimized() -> None:
    policy = get_routing_policy("cost_optimized")
    assert policy.name == RoutingPolicyName.COST_OPTIMIZED
    assert policy.provider_order[0] == ModelProvider.OLLAMA


def test_get_routing_policy_default_balanced() -> None:
    policy = get_routing_policy(None)
    assert policy.name == RoutingPolicyName.BALANCED