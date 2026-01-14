# ai-os/control_plane/decision.py

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class PolicyDecision:
    """
    冻结的裁决结果（Control Plane -> Data Plane 唯一输出）
    约束：
    - allow/reason/capabilities 三要素固定
    - capabilities 用于下游裁剪执行能力（allowed_* / max_tokens / memory_access 等）
    """

    allow: bool
    reason: Optional[str] = None
    capabilities: Dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def allow_with(capabilities: Optional[Dict[str, Any]] = None) -> "PolicyDecision":
        return PolicyDecision(allow=True, reason=None, capabilities=capabilities or {})

    @staticmethod
    def deny(reason: str, capabilities: Optional[Dict[str, Any]] = None) -> "PolicyDecision":
        return PolicyDecision(allow=False, reason=reason, capabilities=capabilities or {})

    def to_dict(self) -> Dict[str, Any]:
        return {
            "allow": self.allow,
            "reason": self.reason,
            "capabilities": self.capabilities,
        }
