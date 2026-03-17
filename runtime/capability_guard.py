from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from .execution_context import ExecutionContext
from .skill_manifest import SkillManifest


@dataclass(slots=True)
class CapabilityGuardDecision:
    allowed: bool
    required_capabilities: List[str] = field(default_factory=list)
    granted_capabilities: List[str] = field(default_factory=list)
    denied_capabilities: List[str] = field(default_factory=list)
    reasons: List[str] = field(default_factory=list)

    @classmethod
    def allow(
        cls,
        *,
        required_capabilities: List[str],
        granted_capabilities: List[str],
    ) -> "CapabilityGuardDecision":
        return cls(
            allowed=True,
            required_capabilities=required_capabilities,
            granted_capabilities=granted_capabilities,
            denied_capabilities=[],
            reasons=[],
        )

    @classmethod
    def deny(
        cls,
        *,
        required_capabilities: List[str],
        granted_capabilities: List[str],
        denied_capabilities: List[str],
        reasons: List[str],
    ) -> "CapabilityGuardDecision":
        return cls(
            allowed=False,
            required_capabilities=required_capabilities,
            granted_capabilities=granted_capabilities,
            denied_capabilities=denied_capabilities,
            reasons=reasons,
        )


class CapabilityGuard:
    """
    Phase 12-A:
    - 将 SkillManifest 中声明的 capabilities 转为运行时强校验
    - allowed_capabilities 由 ExecutionContext 注入
    - 不做兼容猜测，只按明确 capability 名称判断
    """

    def evaluate(
        self,
        *,
        context: ExecutionContext,
        skill: SkillManifest,
    ) -> CapabilityGuardDecision:
        requested_map: Dict[str, bool] = dict(skill.capabilities or {})
        required_capabilities = sorted([k for k, v in requested_map.items() if v])

        if not required_capabilities:
            return CapabilityGuardDecision.allow(
                required_capabilities=[],
                granted_capabilities=[],
            )

        allowed_set = set(str(x) for x in (context.allowed_capabilities or []))

        granted = sorted([cap for cap in required_capabilities if cap in allowed_set])
        denied = sorted([cap for cap in required_capabilities if cap not in allowed_set])

        if denied:
            reasons = [
                (
                    f"Skill '{skill.name}' requires capabilities "
                    f"{', '.join(required_capabilities)} but context only grants "
                    f"{', '.join(sorted(allowed_set)) if allowed_set else '(none)'}; "
                    f"denied: {', '.join(denied)}"
                )
            ]
            return CapabilityGuardDecision.deny(
                required_capabilities=required_capabilities,
                granted_capabilities=granted,
                denied_capabilities=denied,
                reasons=reasons,
            )

        return CapabilityGuardDecision.allow(
            required_capabilities=required_capabilities,
            granted_capabilities=granted,
        )