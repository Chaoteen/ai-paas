from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from control_plane.agent_manifest import AgentManifest


@dataclass(frozen=True)
class AdmissionDecision:
    allow: bool
    reason: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "allow": self.allow,
            "reason": self.reason,
            "metadata": self.metadata,
        }

    @classmethod
    def allow_decision(cls, metadata: Optional[Dict[str, Any]] = None) -> "AdmissionDecision":
        return cls(allow=True, reason=None, metadata=metadata or {})

    @classmethod
    def deny_decision(cls, reason: str, metadata: Optional[Dict[str, Any]] = None) -> "AdmissionDecision":
        return cls(allow=False, reason=reason, metadata=metadata or {})


class AgentAdmission:
    """
    第二轮先实现最基础的 admission：
    - 必填字段
    - endpoint 合法性
    - capabilities 类型检查
    """

    def evaluate(self, manifest: AgentManifest) -> AdmissionDecision:
        if not manifest.name:
            return AdmissionDecision.deny_decision("AGENT_NAME_REQUIRED")

        if not manifest.version:
            return AdmissionDecision.deny_decision("AGENT_VERSION_REQUIRED")

        if not manifest.vendor:
            return AdmissionDecision.deny_decision("AGENT_VENDOR_REQUIRED")

        if not manifest.endpoint:
            return AdmissionDecision.deny_decision("AGENT_ENDPOINT_REQUIRED")

        parsed = urlparse(manifest.endpoint)
        if parsed.scheme not in ("http", "https"):
            return AdmissionDecision.deny_decision("AGENT_ENDPOINT_INVALID_SCHEME")

        if not parsed.netloc:
            return AdmissionDecision.deny_decision("AGENT_ENDPOINT_INVALID")

        if not isinstance(manifest.capabilities, list):
            return AdmissionDecision.deny_decision("AGENT_CAPABILITIES_INVALID")

        if not isinstance(manifest.supported_models, list):
            return AdmissionDecision.deny_decision("AGENT_SUPPORTED_MODELS_INVALID")

        return AdmissionDecision.allow_decision(
            metadata={
                "admission_policy": "basic-agent-admission-v1",
                "runtime": manifest.runtime,
                "protocol_version": manifest.protocol_version,
            }
        )