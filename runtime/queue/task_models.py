from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Type, TypeVar, Union
import uuid


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class TaskType(str, Enum):
    AGENT = "agent"
    GENERATION = "generation"


class TaskStatus(str, Enum):
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELED = "canceled"


class TaskPriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class GenerationTaskKind(str, Enum):
    IMAGE = "image"
    VIDEO = "video"


@dataclass(slots=True)
class AgentTaskPayload:
    agent_id: str
    input: Any
    tenant_id: Optional[str] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    workflow_id: Optional[str] = None
    correlation_id: Optional[str] = None
    routing_policy: Optional[str] = None
    required_capability: Optional[str] = None
    requested_capabilities: List[str] = field(default_factory=list)
    allowed_capabilities: List[str] = field(default_factory=list)
    secrets_scope: List[str] = field(default_factory=list)
    workspace_root: Optional[str] = None
    preferred_skill: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return _deep_serialize(asdict(self))

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentTaskPayload":
        return cls(
            agent_id=data["agent_id"],
            input=data.get("input"),
            tenant_id=data.get("tenant_id"),
            user_id=data.get("user_id"),
            session_id=data.get("session_id"),
            workflow_id=data.get("workflow_id"),
            correlation_id=data.get("correlation_id"),
            routing_policy=data.get("routing_policy"),
            required_capability=data.get("required_capability"),
            requested_capabilities=list(data.get("requested_capabilities", [])),
            allowed_capabilities=list(data.get("allowed_capabilities", [])),
            secrets_scope=list(data.get("secrets_scope", [])),
            workspace_root=data.get("workspace_root"),
            preferred_skill=data.get("preferred_skill"),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass(slots=True)
class GenerationTaskPayload:
    kind: GenerationTaskKind
    prompt: str
    negative_prompt: Optional[str] = None
    provider: Optional[str] = None
    model: Optional[str] = None

    tenant_id: Optional[str] = None
    user_id: Optional[str] = None
    workflow_id: Optional[str] = None
    correlation_id: Optional[str] = None
    routing_policy: Optional[str] = None

    width: Optional[int] = None
    height: Optional[int] = None
    duration_seconds: Optional[int] = None
    fps: Optional[int] = None
    seed: Optional[int] = None
    count: int = 1

    quality: Optional[str] = None
    style: Optional[str] = None
    resolution: Optional[str] = None

    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return _deep_serialize(asdict(self))

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GenerationTaskPayload":
        kind_value = data.get("kind", GenerationTaskKind.IMAGE.value)
        return cls(
            kind=GenerationTaskKind(kind_value),
            prompt=data["prompt"],
            negative_prompt=data.get("negative_prompt"),
            provider=data.get("provider"),
            model=data.get("model"),
            tenant_id=data.get("tenant_id"),
            user_id=data.get("user_id"),
            workflow_id=data.get("workflow_id"),
            correlation_id=data.get("correlation_id"),
            routing_policy=data.get("routing_policy"),
            width=data.get("width"),
            height=data.get("height"),
            duration_seconds=data.get("duration_seconds"),
            fps=data.get("fps"),
            seed=data.get("seed"),
            count=data.get("count", 1),
            quality=data.get("quality"),
            style=data.get("style"),
            resolution=data.get("resolution"),
            metadata=dict(data.get("metadata", {})),
        )


TaskPayload = Union[AgentTaskPayload, GenerationTaskPayload]

T = TypeVar("T", bound="TaskEnvelope")


@dataclass(slots=True)
class TaskEnvelope:
    task_id: str
    task_type: TaskType
    status: TaskStatus
    payload: TaskPayload

    tenant_id: Optional[str] = None
    correlation_id: Optional[str] = None
    workflow_id: Optional[str] = None
    user_id: Optional[str] = None

    priority: TaskPriority = TaskPriority.NORMAL
    queue_name: str = "default"

    retry_count: int = 0
    max_retries: int = 3

    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)
    queued_at: Optional[str] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None

    error: Optional[Dict[str, Any]] = None
    result: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def new_agent_task(
        cls: Type[T],
        payload: AgentTaskPayload,
        *,
        priority: TaskPriority = TaskPriority.NORMAL,
        queue_name: str = "agent",
        max_retries: int = 3,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> T:
        now = utc_now_iso()
        return cls(
            task_id=str(uuid.uuid4()),
            task_type=TaskType.AGENT,
            status=TaskStatus.PENDING,
            payload=payload,
            tenant_id=payload.tenant_id,
            correlation_id=payload.correlation_id,
            workflow_id=payload.workflow_id,
            user_id=payload.user_id,
            priority=priority,
            queue_name=queue_name,
            max_retries=max_retries,
            created_at=now,
            updated_at=now,
            metadata=dict(metadata or {}),
        )

    @classmethod
    def new_generation_task(
        cls: Type[T],
        payload: GenerationTaskPayload,
        *,
        priority: TaskPriority = TaskPriority.NORMAL,
        queue_name: str = "generation",
        max_retries: int = 3,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> T:
        now = utc_now_iso()
        return cls(
            task_id=str(uuid.uuid4()),
            task_type=TaskType.GENERATION,
            status=TaskStatus.PENDING,
            payload=payload,
            tenant_id=payload.tenant_id,
            correlation_id=payload.correlation_id,
            workflow_id=payload.workflow_id,
            user_id=payload.user_id,
            priority=priority,
            queue_name=queue_name,
            max_retries=max_retries,
            created_at=now,
            updated_at=now,
            metadata=dict(metadata or {}),
        )

    def mark_queued(self) -> None:
        now = utc_now_iso()
        self.status = TaskStatus.QUEUED
        self.queued_at = now
        self.updated_at = now

    def mark_running(self) -> None:
        now = utc_now_iso()
        self.status = TaskStatus.RUNNING
        self.started_at = now
        self.updated_at = now

    def mark_succeeded(self, result: Optional[Dict[str, Any]] = None) -> None:
        now = utc_now_iso()
        self.status = TaskStatus.SUCCEEDED
        self.result = dict(result or {})
        self.error = None
        self.finished_at = now
        self.updated_at = now

    def mark_failed(self, error: Optional[Dict[str, Any]] = None) -> None:
        now = utc_now_iso()
        self.status = TaskStatus.FAILED
        self.error = dict(error or {})
        self.finished_at = now
        self.updated_at = now

    def mark_canceled(self, error: Optional[Dict[str, Any]] = None) -> None:
        now = utc_now_iso()
        self.status = TaskStatus.CANCELED
        self.error = dict(error or {})
        self.finished_at = now
        self.updated_at = now

    def increment_retry(self) -> None:
        self.retry_count += 1
        self.updated_at = utc_now_iso()

    @property
    def can_retry(self) -> bool:
        return self.retry_count < self.max_retries

    def to_dict(self) -> Dict[str, Any]:
        payload_dict = self.payload.to_dict()
        return {
            "task_id": self.task_id,
            "task_type": self.task_type.value,
            "status": self.status.value,
            "payload": payload_dict,
            "tenant_id": self.tenant_id,
            "correlation_id": self.correlation_id,
            "workflow_id": self.workflow_id,
            "user_id": self.user_id,
            "priority": self.priority.value,
            "queue_name": self.queue_name,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "queued_at": self.queued_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "error": _deep_serialize(self.error),
            "result": _deep_serialize(self.result),
            "metadata": _deep_serialize(self.metadata),
        }

    @classmethod
    def from_dict(cls: Type[T], data: Dict[str, Any]) -> T:
        task_type = TaskType(data["task_type"])
        payload_data = dict(data["payload"])

        if task_type == TaskType.AGENT:
            payload: TaskPayload = AgentTaskPayload.from_dict(payload_data)
        elif task_type == TaskType.GENERATION:
            payload = GenerationTaskPayload.from_dict(payload_data)
        else:
            raise ValueError(f"Unsupported task_type: {task_type}")

        return cls(
            task_id=data["task_id"],
            task_type=task_type,
            status=TaskStatus(data["status"]),
            payload=payload,
            tenant_id=data.get("tenant_id"),
            correlation_id=data.get("correlation_id"),
            workflow_id=data.get("workflow_id"),
            user_id=data.get("user_id"),
            priority=TaskPriority(data.get("priority", TaskPriority.NORMAL.value)),
            queue_name=data.get("queue_name", "default"),
            retry_count=data.get("retry_count", 0),
            max_retries=data.get("max_retries", 3),
            created_at=data.get("created_at", utc_now_iso()),
            updated_at=data.get("updated_at", utc_now_iso()),
            queued_at=data.get("queued_at"),
            started_at=data.get("started_at"),
            finished_at=data.get("finished_at"),
            error=dict(data["error"]) if data.get("error") else None,
            result=dict(data["result"]) if data.get("result") else None,
            metadata=dict(data.get("metadata", {})),
        )


def _deep_serialize(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return _deep_serialize(asdict(value))
    if isinstance(value, dict):
        return {k: _deep_serialize(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_deep_serialize(v) for v in value]
    if isinstance(value, tuple):
        return [_deep_serialize(v) for v in value]
    return value