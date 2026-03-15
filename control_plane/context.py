from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional
import uuid


def _utcnow_iso() -> str:
    return datetime.utcnow().isoformat()


@dataclass(frozen=True)
class ExecutionContext:
    """
    Control Plane 内部统一执行上下文。

    设计目标：
    1. Control Plane 内部统一语义
    2. 对历史代码兼容：同时支持 input / input_payload
    3. 允许后续扩展 trace_id / session_id / metadata
    """

    request_id: str
    subject: Dict[str, Any]
    action: str
    resource: Dict[str, Any]
    environment: Dict[str, Any]
    input_payload: Dict[str, Any] = field(default_factory=dict)

    trace_id: Optional[str] = None
    session_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=_utcnow_iso)

    @property
    def input(self) -> Dict[str, Any]:
        """
        兼容旧代码：很多地方使用 ctx.input。
        """
        return self.input_payload

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "subject": self.subject,
            "action": self.action,
            "resource": self.resource,
            "environment": self.environment,
            "input": self.input_payload,
            "trace_id": self.trace_id,
            "session_id": self.session_id,
            "metadata": self.metadata,
            "created_at": self.created_at,
        }

    @classmethod
    def from_request_data(cls, request_data: Dict[str, Any]) -> "ExecutionContext":
        request_id = request_data.get("request_id") or f"req_{uuid.uuid4().hex}"

        subject = {
            "type": request_data.get("subject_type", "user"),
            "id": request_data.get("user_id"),
            "tenant_id": request_data.get("tenant_id"),
            "attributes": request_data.get("user_attributes", {}) or {},
        }

        action = request_data.get("action", "prompt.execute")

        resource = {
            "type": request_data.get("resource_type", "prompt"),
            "id": request_data.get("resource_id", "default"),
            "attributes": request_data.get("resource_attributes", {}) or {},
        }

        environment = {
            "region": request_data.get("region", "default"),
            "compliance": request_data.get("compliance", []) or [],
            "timestamp": request_data.get("timestamp") or _utcnow_iso(),
            "source": request_data.get("request_source", "unknown"),
        }

        input_payload = request_data.get("input", {}) or {}

        return cls(
            request_id=request_id,
            subject=subject,
            action=action,
            resource=resource,
            environment=environment,
            input_payload=input_payload,
            trace_id=request_data.get("trace_id"),
            session_id=request_data.get("session_id"),
            metadata=request_data.get("metadata", {}) or {},
        )