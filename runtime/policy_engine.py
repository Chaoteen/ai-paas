from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from .execution_context import ExecutionContext
from .skill_manifest import SkillManifest


@dataclass(slots=True)
class PolicyDecision:
    allowed: bool
    reasons: List[str] = field(default_factory=list)
    granted_capabilities: List[str] = field(default_factory=list)

    @classmethod
    def allow(cls, granted_capabilities: List[str]) -> "PolicyDecision":
        return cls(allowed=True, reasons=[], granted_capabilities=granted_capabilities)

    @classmethod
    def deny(cls, *reasons: str) -> "PolicyDecision":
        return cls(allowed=False, reasons=list(reasons), granted_capabilities=[])


class PolicyEngine:
    """
    Phase 10 先用本地规则。
    Phase 12 再扩展为 OPA / ABAC 对接。
    """

    DEFAULT_ALLOWED = {
        "filesystem_read": False,
        "filesystem_write": False,
        "network": False,
        "shell": False,
        "secrets": False,
    }

    def evaluate(self, *, context: ExecutionContext, skill: SkillManifest) -> PolicyDecision:
        requested = skill.capabilities or {}
        allowed_map: Dict[str, bool] = dict(self.DEFAULT_ALLOWED)

        for cap in context.allowed_capabilities:
            allowed_map[cap] = True

        denied: List[str] = []
        granted: List[str] = []

        for cap_name, enabled in requested.items():
            if not enabled:
                continue
            if allowed_map.get(cap_name, False):
                granted.append(cap_name)
            else:
                denied.append(cap_name)

        if denied:
            return PolicyDecision.deny(
                f"Skill '{skill.name}' requested unauthorized capabilities: {', '.join(sorted(denied))}"
            )

        return PolicyDecision.allow(sorted(granted))