from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


def workflow_utcnow() -> datetime:
    return datetime.now(timezone.utc)


class CapabilityKind(str, Enum):
    AGENT = "agent"
    SKILL = "skill"
    MODEL = "model"
    GENERATION = "generation"
    CONNECTOR = "connector"
    WORKFLOW = "workflow"


class WorkflowNodeType(str, Enum):
    START = "start"
    CAPABILITY = "capability"
    DECISION = "decision"
    PARALLEL = "parallel"
    JOIN = "join"
    END = "end"
    SUBWORKFLOW = "subworkflow"
    WAIT_EVENT = "wait_event"


class WorkflowDefinitionStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    DISABLED = "disabled"


class WorkflowExecutionStatus(str, Enum):
    CREATED = "created"
    QUEUED = "queued"
    RUNNING = "running"
    WAITING = "waiting"
    COMPENSATING = "compensating"
    CANCELLED = "cancelled"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    PARTIAL_FAILED = "partial_failed"


class WorkflowStepExecutionStatus(str, Enum):
    CREATED = "created"
    READY = "ready"
    RUNNING = "running"
    WAITING = "waiting"
    RETRYING = "retrying"
    COMPENSATING = "compensating"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


class WorkflowExecutionEventType(str, Enum):
    EXECUTION_CREATED = "execution.created"
    EXECUTION_QUEUED = "execution.queued"
    EXECUTION_RUNNING = "execution.running"
    EXECUTION_WAITING = "execution.waiting"
    EXECUTION_SUCCEEDED = "execution.succeeded"
    EXECUTION_FAILED = "execution.failed"
    STEP_CREATED = "step.created"
    STEP_RUNNING = "step.running"
    STEP_RETRYING = "step.retrying"
    STEP_SUCCEEDED = "step.succeeded"
    STEP_FAILED = "step.failed"
    STEP_SKIPPED = "step.skipped"


class CapabilityRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: CapabilityKind
    key: str = Field(..., min_length=1)
    version: str = Field(..., min_length=1)

    @field_validator("key", "version")
    @classmethod
    def _validate_non_empty(cls, value: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("value must be a non-empty string")
        return value.strip()


class RetryPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_attempts: int = Field(default=1, ge=1)
    backoff_seconds: int = Field(default=0, ge=0)
    strategy: str = Field(default="fixed", min_length=1)


class TimeoutPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    timeout_seconds: int = Field(default=300, ge=1)


class CompensationPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    capability_ref: Optional[CapabilityRef] = None


class WorkflowNode(BaseModel):
    model_config = ConfigDict(extra="allow")

    node_id: str = Field(..., min_length=1)
    node_type: WorkflowNodeType
    name: str = Field(..., min_length=1)

    capability_ref: Optional[CapabilityRef] = None
    input_mapping: Dict[str, Any] = Field(default_factory=dict)
    output_mapping: Dict[str, Any] = Field(default_factory=dict)
    condition: Optional[str] = None

    retry_policy: RetryPolicy = Field(default_factory=RetryPolicy)
    timeout_policy: TimeoutPolicy = Field(default_factory=TimeoutPolicy)
    compensation_policy: CompensationPolicy = Field(default_factory=CompensationPolicy)

    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("node_id", "name")
    @classmethod
    def _validate_required_strings(cls, value: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("value must be a non-empty string")
        return value.strip()


class WorkflowEdge(BaseModel):
    model_config = ConfigDict(extra="forbid")

    edge_id: str = Field(..., min_length=1)
    source_node_id: str = Field(..., min_length=1)
    target_node_id: str = Field(..., min_length=1)
    condition: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("edge_id", "source_node_id", "target_node_id")
    @classmethod
    def _validate_required_strings(cls, value: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("value must be a non-empty string")
        return value.strip()


class WorkflowDefinition(BaseModel):
    model_config = ConfigDict(extra="allow")

    workflow_key: str = Field(..., min_length=1)
    workflow_version: str = Field(..., min_length=1)
    display_name: str = Field(..., min_length=1)
    status: WorkflowDefinitionStatus = WorkflowDefinitionStatus.DRAFT

    input_schema: Dict[str, Any] = Field(default_factory=dict)
    output_schema: Dict[str, Any] = Field(default_factory=dict)
    nodes: List[WorkflowNode] = Field(default_factory=list)
    edges: List[WorkflowEdge] = Field(default_factory=list)

    policies: Dict[str, Any] = Field(default_factory=dict)
    governance: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    checksum: Optional[str] = None
    created_by: Optional[str] = None
    updated_by: Optional[str] = None

    created_at: datetime = Field(default_factory=workflow_utcnow)
    updated_at: datetime = Field(default_factory=workflow_utcnow)

    @field_validator("workflow_key", "workflow_version", "display_name")
    @classmethod
    def _validate_required_strings(cls, value: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("value must be a non-empty string")
        return value.strip()

    def to_schema_json(self) -> Dict[str, Any]:
        return self.model_dump(mode="json")


class WorkflowExecution(BaseModel):
    model_config = ConfigDict(extra="allow")

    workflow_execution_id: str = Field(..., min_length=1)
    task_id: str = Field(..., min_length=1)
    tenant_id: str = Field(..., min_length=1)

    workflow_key: str = Field(..., min_length=1)
    workflow_version: str = Field(..., min_length=1)
    definition_snapshot_json: Dict[str, Any] = Field(default_factory=dict)

    status: WorkflowExecutionStatus = WorkflowExecutionStatus.CREATED
    input_json: Dict[str, Any] = Field(default_factory=dict)
    context_json: Dict[str, Any] = Field(default_factory=dict)
    system_context_json: Dict[str, Any] = Field(default_factory=dict)
    output_json: Optional[Dict[str, Any]] = None
    error_text: Optional[str] = None

    active_node_ids: List[str] = Field(default_factory=list)
    resolved_capabilities_json: Dict[str, Any] = Field(default_factory=dict)
    governance_json: Dict[str, Any] = Field(default_factory=dict)
    trace_json: Dict[str, Any] = Field(default_factory=dict)

    created_at: datetime = Field(default_factory=workflow_utcnow)
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    updated_at: datetime = Field(default_factory=workflow_utcnow)


class WorkflowStepExecution(BaseModel):
    model_config = ConfigDict(extra="allow")

    workflow_step_execution_id: str = Field(..., min_length=1)
    workflow_execution_id: str = Field(..., min_length=1)

    node_id: str = Field(..., min_length=1)
    node_type: str = Field(..., min_length=1)
    capability_ref_json: Dict[str, Any] = Field(default_factory=dict)

    status: WorkflowStepExecutionStatus = WorkflowStepExecutionStatus.CREATED
    attempt_no: int = Field(default=1, ge=1)
    input_json: Dict[str, Any] = Field(default_factory=dict)
    output_json: Optional[Dict[str, Any]] = None
    error_text: Optional[str] = None

    retry_policy_json: Dict[str, Any] = Field(default_factory=dict)
    timeout_policy_json: Dict[str, Any] = Field(default_factory=dict)
    compensation_policy_json: Dict[str, Any] = Field(default_factory=dict)
    trace_json: Dict[str, Any] = Field(default_factory=dict)

    created_at: datetime = Field(default_factory=workflow_utcnow)
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    updated_at: datetime = Field(default_factory=workflow_utcnow)


class WorkflowExecutionEvent(BaseModel):
    model_config = ConfigDict(extra="allow")

    workflow_execution_event_id: Optional[int] = None
    workflow_execution_id: str = Field(..., min_length=1)
    workflow_step_execution_id: Optional[str] = None
    tenant_id: str = Field(..., min_length=1)

    event_type: WorkflowExecutionEventType
    payload_json: Dict[str, Any] = Field(default_factory=dict)

    created_at: datetime = Field(default_factory=workflow_utcnow)