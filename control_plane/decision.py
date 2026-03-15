from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class PolicyDecision:
    """
    Control Plane -> Data Plane 的冻结授权结果。

    统一字段：
    - allow: 是否放行
    - reason: 拒绝原因或补充说明
    - capabilities: 裁剪后的能力集合
    - obligations: 平台要求执行的附加义务
    - metadata: 额外调试/审计字段
    """

    allow: bool
    reason: Optional[str] = None
    capabilities: Dict[str, Any] = field(default_factory=dict)
    obligations: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.allow

    def to_dict(self) -> Dict[str, Any]:
        return {
            "allow": self.allow,
            "reason": self.reason,
            "capabilities": self.capabilities,
            "obligations": self.obligations,
            "metadata": self.metadata,
        }

    @classmethod
    def allow_decision(
        cls,
        capabilities: Optional[Dict[str, Any]] = None,
        obligations: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "PolicyDecision":
        return cls(
            allow=True,
            reason=None,
            capabilities=capabilities or {},
            obligations=obligations or {},
            metadata=metadata or {},
        )

    @classmethod
    def deny_decision(
        cls,
        reason: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "PolicyDecision":
        return cls(
            allow=False,
            reason=reason,
            capabilities={},
            obligations={},
            metadata=metadata or {},
        )