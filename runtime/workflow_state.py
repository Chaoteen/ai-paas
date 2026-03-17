from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


TASK_STATUS_SUBMITTED = "submitted"
TASK_STATUS_ROUTED = "routed"
TASK_STATUS_EXECUTING = "executing"
TASK_STATUS_COMPLETED = "completed"
TASK_STATUS_FAILED = "failed"

FINAL_TASK_STATUSES = {
    TASK_STATUS_COMPLETED,
    TASK_STATUS_FAILED,
}

ALLOWED_TASK_TRANSITIONS = {
    TASK_STATUS_SUBMITTED: {TASK_STATUS_ROUTED, TASK_STATUS_EXECUTING, TASK_STATUS_FAILED},
    TASK_STATUS_ROUTED: {TASK_STATUS_EXECUTING, TASK_STATUS_FAILED},
    TASK_STATUS_EXECUTING: {TASK_STATUS_COMPLETED, TASK_STATUS_FAILED},
    TASK_STATUS_COMPLETED: set(),
    TASK_STATUS_FAILED: set(),
}


@dataclass(slots=True)
class TaskState:
    task_id: str
    tenant_id: str
    workflow_id: Optional[str] = None
    correlation_id: Optional[str] = None
    status: str = TASK_STATUS_SUBMITTED
    selected_agent_id: Optional[str] = None
    selected_skill: Optional[str] = None
    last_event_type: Optional[str] = None
    input_payload: Dict[str, Any] = field(default_factory=dict)
    output_payload: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    retry_count: int = 0
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)
    completed_at: Optional[str] = None

    def can_transition_to(self, new_status: str) -> bool:
        if self.status == new_status:
            return True
        allowed = ALLOWED_TASK_TRANSITIONS.get(self.status, set())
        return new_status in allowed

    def transition_to(
        self,
        new_status: str,
        *,
        event_type: Optional[str] = None,
        selected_agent_id: Optional[str] = None,
        selected_skill: Optional[str] = None,
        output_payload: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        metadata_patch: Optional[Dict[str, Any]] = None,
    ) -> None:
        if not self.can_transition_to(new_status):
            raise ValueError(
                f"Illegal task state transition: {self.status} -> {new_status} for task_id={self.task_id}"
            )

        self.status = new_status
        self.last_event_type = event_type or self.last_event_type

        if selected_agent_id is not None:
            self.selected_agent_id = selected_agent_id
        if selected_skill is not None:
            self.selected_skill = selected_skill
        if output_payload is not None:
            self.output_payload = dict(output_payload)
        if error is not None:
            self.error = error
        if metadata_patch:
            self.metadata.update(metadata_patch)

        self.updated_at = utc_now_iso()
        if new_status in FINAL_TASK_STATUSES:
            self.completed_at = utc_now_iso()

    def is_final(self) -> bool:
        return self.status in FINAL_TASK_STATUSES

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "tenant_id": self.tenant_id,
            "workflow_id": self.workflow_id,
            "correlation_id": self.correlation_id,
            "status": self.status,
            "selected_agent_id": self.selected_agent_id,
            "selected_skill": self.selected_skill,
            "last_event_type": self.last_event_type,
            "input_payload": dict(self.input_payload),
            "output_payload": dict(self.output_payload),
            "error": self.error,
            "metadata": dict(self.metadata),
            "retry_count": self.retry_count,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "completed_at": self.completed_at,
        }


@dataclass(slots=True)
class WorkflowState:
    workflow_id: str
    tenant_id: str
    correlation_id: Optional[str] = None
    status: str = "running"
    task_ids: list[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)
    completed_at: Optional[str] = None

    def add_task(self, task_id: str) -> None:
        if task_id not in self.task_ids:
            self.task_ids.append(task_id)
            self.updated_at = utc_now_iso()

    def mark_completed(self) -> None:
        self.status = "completed"
        self.updated_at = utc_now_iso()
        self.completed_at = utc_now_iso()

    def mark_failed(self, reason: Optional[str] = None) -> None:
        self.status = "failed"
        if reason:
            self.metadata["reason"] = reason
        self.updated_at = utc_now_iso()
        self.completed_at = utc_now_iso()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "tenant_id": self.tenant_id,
            "correlation_id": self.correlation_id,
            "status": self.status,
            "task_ids": list(self.task_ids),
            "metadata": dict(self.metadata),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "completed_at": self.completed_at,
        }