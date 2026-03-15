from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict
import uuid


def _utcnow_iso() -> str:
    return datetime.utcnow().isoformat()


@dataclass(frozen=True)
class ControlEvent:
    """
    Control Plane 标准事件对象。
    """

    event_id: str
    event_type: str
    aggregate_type: str
    aggregate_id: str
    payload: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=_utcnow_iso)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "aggregate_type": self.aggregate_type,
            "aggregate_id": self.aggregate_id,
            "payload": self.payload,
            "metadata": self.metadata,
            "created_at": self.created_at,
        }

    @classmethod
    def new(
        cls,
        *,
        event_type: str,
        aggregate_type: str,
        aggregate_id: str,
        payload: Dict[str, Any] | None = None,
        metadata: Dict[str, Any] | None = None,
    ) -> "ControlEvent":
        return cls(
            event_id=f"evt_{uuid.uuid4().hex}",
            event_type=event_type,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            payload=payload or {},
            metadata=metadata or {},
        )