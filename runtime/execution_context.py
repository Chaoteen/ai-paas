from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True)
class ExecutionContext:
    task_id: str
    tenant_id: str
    workflow_id: Optional[str] = None
    correlation_id: Optional[str] = None
    user_id: Optional[str] = None
    selected_agent_id: Optional[str] = None
    required_capability: Optional[str] = None
    workspace_root: Optional[str] = None
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    requested_capabilities: List[str] = field(default_factory=list)
    allowed_capabilities: List[str] = field(default_factory=list)
    secrets_scope: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    input_payload: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now_iso)
    deadline_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "tenant_id": self.tenant_id,
            "workflow_id": self.workflow_id,
            "correlation_id": self.correlation_id,
            "user_id": self.user_id,
            "selected_agent_id": self.selected_agent_id,
            "required_capability": self.required_capability,
            "workspace_root": self.workspace_root,
            "trace_id": self.trace_id,
            "requested_capabilities": list(self.requested_capabilities),
            "allowed_capabilities": list(self.allowed_capabilities),
            "secrets_scope": list(self.secrets_scope),
            "metadata": dict(self.metadata),
            "input_payload": dict(self.input_payload),
            "created_at": self.created_at,
            "deadline_at": self.deadline_at,
        }