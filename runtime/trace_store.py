from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(slots=True)
class TraceEvent:
    event_type: str
    task_id: Optional[str]
    workflow_id: Optional[str]
    tenant_id: Optional[str]
    correlation_id: Optional[str]
    source: Optional[str]
    payload: Dict[str, Any] = field(default_factory=dict)
    occurred_at: Optional[str] = None
    event_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type,
            "task_id": self.task_id,
            "workflow_id": self.workflow_id,
            "tenant_id": self.tenant_id,
            "correlation_id": self.correlation_id,
            "source": self.source,
            "payload": dict(self.payload),
            "occurred_at": self.occurred_at,
            "event_id": self.event_id,
        }


class InMemoryTraceStore:
    def __init__(self) -> None:
        self._by_task: Dict[str, List[TraceEvent]] = {}

    async def append_event(self, event: Dict[str, Any]) -> None:
        task_id = event.get("task_id")
        if not task_id:
            return

        item = TraceEvent(
            event_type=str(event.get("event_type")),
            task_id=task_id,
            workflow_id=event.get("workflow_id"),
            tenant_id=event.get("tenant_id"),
            correlation_id=event.get("correlation_id"),
            source=event.get("source"),
            payload=dict(event.get("payload", {}) or {}),
            occurred_at=event.get("occurred_at"),
            event_id=event.get("id") or event.get("event_id"),
        )
        self._by_task.setdefault(task_id, []).append(item)

    async def get_trace(self, task_id: str) -> List[TraceEvent]:
        return list(self._by_task.get(task_id, []))

    async def list_task_ids(self) -> List[str]:
        return sorted(self._by_task.keys())