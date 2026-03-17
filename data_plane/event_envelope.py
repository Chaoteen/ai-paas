from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional
import uuid


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class EventEnvelope:
    """
    Phase 8 / 方案A终态：
    全系统统一只使用 id 作为事件唯一主标识
    """

    id: str
    event_type: str
    stream: str
    source: str
    payload: Dict[str, Any]

    tenant_id: Optional[str] = None
    correlation_id: Optional[str] = None
    task_id: Optional[str] = None
    workflow_id: Optional[str] = None
    headers: Dict[str, Any] = field(default_factory=dict)
    occurred_at: str = field(default_factory=utc_now_iso)
    schema_version: str = "1.0"
    retry_count: int = 0

    @classmethod
    def new(
        cls,
        *,
        event_type: str,
        stream: str,
        source: str,
        payload: Dict[str, Any],
        tenant_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        task_id: Optional[str] = None,
        workflow_id: Optional[str] = None,
        headers: Optional[Dict[str, Any]] = None,
        schema_version: str = "1.0",
    ) -> "EventEnvelope":
        return cls(
            id=str(uuid.uuid4()),
            event_type=event_type,
            stream=stream,
            source=source,
            payload=payload,
            tenant_id=tenant_id,
            correlation_id=correlation_id,
            task_id=task_id,
            workflow_id=workflow_id,
            headers=headers or {},
            schema_version=schema_version,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "event_type": self.event_type,
            "stream": self.stream,
            "source": self.source,
            "payload": self.payload,
            "tenant_id": self.tenant_id,
            "correlation_id": self.correlation_id,
            "task_id": self.task_id,
            "workflow_id": self.workflow_id,
            "headers": self.headers,
            "occurred_at": self.occurred_at,
            "schema_version": self.schema_version,
            "retry_count": self.retry_count,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EventEnvelope":
        return cls(
            id=data["id"],
            event_type=data["event_type"],
            stream=data["stream"],
            source=data["source"],
            payload=data["payload"],
            tenant_id=data.get("tenant_id"),
            correlation_id=data.get("correlation_id"),
            task_id=data.get("task_id"),
            workflow_id=data.get("workflow_id"),
            headers=data.get("headers", {}),
            occurred_at=data.get("occurred_at", utc_now_iso()),
            schema_version=data.get("schema_version", "1.0"),
            retry_count=int(data.get("retry_count", 0)),
        )