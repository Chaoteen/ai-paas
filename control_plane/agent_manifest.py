from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid


def _utcnow_iso() -> str:
    return datetime.utcnow().isoformat()


@dataclass(frozen=True)
class AgentManifest:
    """
    Agent 启动时上报的标准描述。
    """

    name: str
    version: str
    vendor: str
    capabilities: List[str] = field(default_factory=list)
    supported_models: List[str] = field(default_factory=list)
    endpoint: str = ""
    runtime: str = "custom"
    protocol_version: str = "v1"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "vendor": self.vendor,
            "capabilities": self.capabilities,
            "supported_models": self.supported_models,
            "endpoint": self.endpoint,
            "runtime": self.runtime,
            "protocol_version": self.protocol_version,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentManifest":
        return cls(
            name=(data.get("name") or "").strip(),
            version=(data.get("version") or "").strip(),
            vendor=(data.get("vendor") or "").strip(),
            capabilities=list(data.get("capabilities") or []),
            supported_models=list(data.get("supported_models") or []),
            endpoint=(data.get("endpoint") or "").strip(),
            runtime=(data.get("runtime") or "custom").strip(),
            protocol_version=(data.get("protocol_version") or "v1").strip(),
            metadata=dict(data.get("metadata") or {}),
        )


@dataclass
class AgentRecord:
    """
    Registry 内部保存的 Agent 记录。
    """

    agent_id: str
    manifest: AgentManifest
    status: str = "online"
    created_at: str = field(default_factory=_utcnow_iso)
    updated_at: str = field(default_factory=_utcnow_iso)
    last_heartbeat: Optional[str] = None

    @property
    def name(self) -> str:
        return self.manifest.name

    @property
    def version(self) -> str:
        return self.manifest.version

    @property
    def vendor(self) -> str:
        return self.manifest.vendor

    def touch(self):
        now = _utcnow_iso()
        self.updated_at = now
        self.last_heartbeat = now

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "last_heartbeat": self.last_heartbeat,
            "manifest": self.manifest.to_dict(),
        }

    @classmethod
    def new(cls, manifest: AgentManifest) -> "AgentRecord":
        return cls(
            agent_id=f"agt_{uuid.uuid4().hex}",
            manifest=manifest,
            status="online",
        )