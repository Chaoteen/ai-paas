from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TaskStatus(str, Enum):
    CREATED = "created"
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class TaskType(str, Enum):
    AGENT = "agent"
    GENERATION = "generation"


class AgentTaskPayload(BaseModel):
    """
    Agent runtime input payload.

    extra='allow' is intentional:
    - preserves forward compatibility for evolving runtime inputs
    - avoids breaking callers when new optional fields are introduced
    """

    model_config = ConfigDict(extra="allow")

    prompt: str = Field(..., min_length=1)
    model: str = Field(..., min_length=1)
    system_prompt: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("prompt", "model")
    @classmethod
    def _validate_non_empty(cls, value: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("value must be a non-empty string")
        return value.strip()


class GenerationTaskPayload(BaseModel):
    """
    Generation runtime input payload.

    Kept intentionally broad because image/video generation providers
    often diverge in parameter surface.
    """

    model_config = ConfigDict(extra="allow")

    prompt: str = Field(..., min_length=1)
    model: str = Field(..., min_length=1)
    modality: str = Field(..., min_length=1)  # image | video | future types
    size: Optional[str] = None
    duration_seconds: Optional[int] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("prompt", "model", "modality")
    @classmethod
    def _validate_non_empty(cls, value: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("value must be a non-empty string")
        return value.strip()


class TaskEnvelope(BaseModel):
    """
    Canonical task envelope used across gateway, queue, worker and store.

    Design goals:
    1. Stable serialization shape for queue and persistence layers.
    2. Explicit lifecycle transitions with timestamp capture.
    3. Strict top-level schema, flexible payload schema.
    """

    model_config = ConfigDict(extra="forbid", use_enum_values=False)

    task_id: str = Field(..., min_length=1)
    tenant_id: str = Field(..., min_length=1)
    task_type: TaskType
    queue_name: str = Field(..., min_length=1)
    status: TaskStatus = TaskStatus.CREATED

    payload: Dict[str, Any] = Field(default_factory=dict)
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

    created_at: datetime = Field(default_factory=utcnow)
    queued_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None

    retry_count: int = 0
    correlation_id: Optional[str] = None
    idempotency_key: Optional[str] = None

    @field_validator("task_id", "tenant_id", "queue_name")
    @classmethod
    def _validate_required_strings(cls, value: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("value must be a non-empty string")
        return value.strip()

    @classmethod
    def for_agent(
        cls,
        *,
        tenant_id: str,
        payload: AgentTaskPayload,
        queue_name: str = "agent_tasks",
        correlation_id: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> "TaskEnvelope":
        return cls(
            task_id=str(uuid4()),
            tenant_id=tenant_id,
            task_type=TaskType.AGENT,
            queue_name=queue_name,
            status=TaskStatus.CREATED,
            payload=payload.model_dump(mode="json"),
            correlation_id=correlation_id,
            idempotency_key=idempotency_key,
        )

    @classmethod
    def for_generation(
        cls,
        *,
        tenant_id: str,
        payload: GenerationTaskPayload,
        queue_name: str = "generation_tasks",
        correlation_id: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> "TaskEnvelope":
        return cls(
            task_id=str(uuid4()),
            tenant_id=tenant_id,
            task_type=TaskType.GENERATION,
            queue_name=queue_name,
            status=TaskStatus.CREATED,
            payload=payload.model_dump(mode="json"),
            correlation_id=correlation_id,
            idempotency_key=idempotency_key,
        )

    def mark_queued(self) -> None:
        self.status = TaskStatus.QUEUED
        self.queued_at = utcnow()
        self.error = None

    def mark_running(self) -> None:
        self.status = TaskStatus.RUNNING
        self.started_at = utcnow()
        self.error = None

    def mark_succeeded(self, result: Dict[str, Any]) -> None:
        if not isinstance(result, dict):
            raise ValueError("result must be a dict")
        self.status = TaskStatus.SUCCEEDED
        self.result = result
        self.error = None
        self.finished_at = utcnow()

    def mark_failed(self, error: Any) -> None:
        self.status = TaskStatus.FAILED
        self.finished_at = utcnow()

        if error is None:
            self.error = "unknown error"
            return

        if isinstance(error, str):
            self.error = error
            return

        if isinstance(error, dict):
            error_type = error.get("type", "error")
            error_message = error.get("message", "")
            if error_message:
                self.error = f"{error_type}: {error_message}"
            else:
                self.error = str(error_type)
            return

        self.error = str(error)

    def increment_retry(self) -> None:
        self.retry_count += 1

    def as_queue_message(self) -> Dict[str, Any]:
        """
        Stable queue payload shape for Redis Streams or other brokers.
        """
        return self.model_dump(mode="json")