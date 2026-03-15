from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict
import uuid


def _utcnow_iso() -> str:
    return datetime.utcnow().isoformat()


@dataclass(frozen=True)
class DataEvent:
    """
    Data Plane 标准事件对象。
    """

    event_id: str
    event_type: str
    task_id: str
    envelope_id: str
    payload: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=_utcnow_iso)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "task_id": self.task_id,
            "envelope_id": self.envelope_id,
            "payload": self.payload,
            "metadata": self.metadata,
            "created_at": self.created_at,
        }

    @classmethod
    def new(
        cls,
        *,
        event_type: str,
        task_id: str,
        envelope_id: str,
        payload: Dict[str, Any] | None = None,
        metadata: Dict[str, Any] | None = None,
    ) -> "DataEvent":
        return cls(
            event_id=f"devt_{uuid.uuid4().hex}",
            event_type=event_type,
            task_id=task_id,
            envelope_id=envelope_id,
            payload=payload or {},
            metadata=metadata or {},
        )