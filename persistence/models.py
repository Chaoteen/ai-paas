from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import DateTime, Index, Integer, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class RuntimeTaskRecord(Base):
    """
    Durable task state for async runtime.

    This table is the source of truth for task lifecycle state.
    It is intentionally normalized around the queue/task contract used by:
    - gateway submit APIs
    - task dispatcher
    - worker runtime
    - outbox relay / retry orchestration
    """

    __tablename__ = "runtime_tasks"

    task_id: Mapped[str] = mapped_column(primary_key=True)
    tenant_id: Mapped[str] = mapped_column(index=True)
    task_type: Mapped[str] = mapped_column(index=False)
    queue_name: Mapped[str] = mapped_column(index=False)
    status: Mapped[str] = mapped_column(index=True)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSONB)
    result_json: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    error_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    correlation_id: Mapped[Optional[str]] = mapped_column(nullable=True, index=True)
    idempotency_key: Mapped[Optional[str]] = mapped_column(nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    queued_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    finished_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "idempotency_key",
            name="uq_runtime_tasks_tenant_idempotency_key",
        ),
        Index(
            "idx_runtime_tasks_queue_name_status",
            "queue_name",
            "status",
        ),
        Index(
            "idx_runtime_tasks_created_at",
            "created_at",
        ),
    )


class RuntimeOutboxEventRecord(Base):
    """
    Transactional outbox for durable broker publish.

    Each row represents a domain event that must be published after the
    enclosing DB transaction commits successfully.
    """

    __tablename__ = "runtime_outbox_events"

    event_id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    aggregate_type: Mapped[str] = mapped_column(nullable=False)
    aggregate_id: Mapped[str] = mapped_column(nullable=False, index=True)
    tenant_id: Mapped[str] = mapped_column(nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(nullable=False)
    queue_name: Mapped[str] = mapped_column(nullable=False)
    stream_name: Mapped[str] = mapped_column(nullable=False)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(nullable=False, default="pending")
    publish_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    published_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        UniqueConstraint(
            "aggregate_type",
            "aggregate_id",
            "event_type",
            name="uq_runtime_outbox_task_queued_once",
        ),
        Index(
            "idx_runtime_outbox_status_available_at",
            "status",
            "available_at",
            "event_id",
        ),
        Index(
            "idx_runtime_outbox_created_at",
            "created_at",
        ),
    )


class WorkflowDefinitionRecord(Base):
    """Registered workflow definition and versioned schema source of truth."""

    __tablename__ = "workflow_definitions"

    workflow_key: Mapped[str] = mapped_column(primary_key=True)
    workflow_version: Mapped[str] = mapped_column(primary_key=True)
    display_name: Mapped[str] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(nullable=False, index=True)
    schema_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    input_schema_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    output_schema_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    policies_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    governance_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    checksum: Mapped[Optional[str]] = mapped_column(nullable=True)
    created_by: Mapped[Optional[str]] = mapped_column(nullable=True)
    updated_by: Mapped[Optional[str]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("idx_workflow_definitions_status", "status"),
        Index("idx_workflow_definitions_created_at", "created_at"),
    )


class WorkflowExecutionRecord(Base):
    """Durable workflow execution instance linked to runtime_tasks."""

    __tablename__ = "workflow_executions"

    workflow_execution_id: Mapped[str] = mapped_column(primary_key=True)
    task_id: Mapped[str] = mapped_column(nullable=False, unique=True, index=True)
    tenant_id: Mapped[str] = mapped_column(nullable=False, index=True)
    workflow_key: Mapped[str] = mapped_column(nullable=False)
    workflow_version: Mapped[str] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(nullable=False, index=True)
    definition_snapshot_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    input_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    context_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    system_context_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    output_json: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    error_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    active_node_ids: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)
    resolved_capabilities_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    governance_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    trace_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("idx_workflow_executions_tenant_status", "tenant_id", "status"),
        Index("idx_workflow_executions_definition", "workflow_key", "workflow_version"),
        Index("idx_workflow_executions_created_at", "created_at"),
    )


class WorkflowStepExecutionRecord(Base):
    """Durable per-node execution state inside a workflow execution."""

    __tablename__ = "workflow_step_executions"

    workflow_step_execution_id: Mapped[str] = mapped_column(primary_key=True)
    workflow_execution_id: Mapped[str] = mapped_column(nullable=False, index=True)
    node_id: Mapped[str] = mapped_column(nullable=False)
    node_type: Mapped[str] = mapped_column(nullable=False)
    capability_ref_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(nullable=False, index=True)
    attempt_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    input_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    output_json: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    error_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    retry_policy_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    timeout_policy_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    compensation_policy_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    trace_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("idx_workflow_step_executions_execution_status", "workflow_execution_id", "status"),
        Index("idx_workflow_step_executions_node_attempt", "workflow_execution_id", "node_id", "attempt_no"),
    )


class WorkflowExecutionEventRecord(Base):
    """Append-only workflow execution event log for audit / replay / tracing."""

    __tablename__ = "workflow_execution_events"

    workflow_execution_event_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workflow_execution_id: Mapped[str] = mapped_column(nullable=False, index=True)
    workflow_step_execution_id: Mapped[Optional[str]] = mapped_column(nullable=True, index=True)
    tenant_id: Mapped[str] = mapped_column(nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(nullable=False, index=True)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        Index(
            "idx_workflow_execution_events_execution_created_at",
            "workflow_execution_id",
            "created_at",
        ),
    )


class WorkflowProductRecord(Base):
    __tablename__ = "workflow_products"

    product_key: Mapped[str] = mapped_column(primary_key=True)
    product_version: Mapped[str] = mapped_column(primary_key=True)

    display_name: Mapped[str] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(nullable=False, index=True)

    public_api_schema_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )
    ui_schema_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )

    bound_workflow_key: Mapped[str] = mapped_column(nullable=False, index=True)
    bound_workflow_version: Mapped[str] = mapped_column(nullable=False)

    default_input_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )
    default_context_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )
    input_mapping_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )

    governance_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )

    visibility: Mapped[str] = mapped_column(nullable=False, default="tenant")

    created_by: Mapped[Optional[str]] = mapped_column(nullable=True)
    updated_by: Mapped[Optional[str]] = mapped_column(nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        Index("idx_workflow_products_status", "status"),
        Index(
            "idx_workflow_products_workflow_binding",
            "bound_workflow_key",
            "bound_workflow_version",
        ),
    )

class RecordingSessionRecord(Base):
    __tablename__ = "recording_sessions"

    recording_session_id: Mapped[str] = mapped_column(primary_key=True)
    tenant_id: Mapped[str] = mapped_column(nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(nullable=False, index=True)
    distillation_mode: Mapped[str] = mapped_column(nullable=False, default="dialogue_only")
    current_phase: Mapped[str] = mapped_column(nullable=False, default="capture")
    title: Mapped[str] = mapped_column(nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    context_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    source_metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    latest_skill_draft_id: Mapped[Optional[str]] = mapped_column(nullable=True)
    created_by: Mapped[Optional[str]] = mapped_column(nullable=True)
    updated_by: Mapped[Optional[str]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        Index("idx_recording_sessions_tenant_created_at", "tenant_id", "created_at"),
        Index("idx_recording_sessions_tenant_status_created_at", "tenant_id", "status", "created_at"),
        Index("idx_recording_sessions_tenant_source_created_at", "tenant_id", "source_type", "created_at"),
    )


class RecordingActionEventRecord(Base):
    __tablename__ = "recording_action_events"

    recording_action_event_id: Mapped[str] = mapped_column(primary_key=True)
    recording_session_id: Mapped[str] = mapped_column(nullable=False, index=True)
    tenant_id: Mapped[str] = mapped_column(nullable=False, index=True)
    sequence_no: Mapped[int] = mapped_column(Integer, nullable=False)
    idempotency_key: Mapped[Optional[str]] = mapped_column(nullable=True)
    source_event_id: Mapped[Optional[str]] = mapped_column(nullable=True)
    event_timestamp: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    event_type: Mapped[str] = mapped_column(nullable=False, index=True)
    actor_type: Mapped[str] = mapped_column(nullable=False)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    source_ref_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    __table_args__ = (
        UniqueConstraint(
            "recording_session_id",
            "sequence_no",
            name="uq_recording_action_events_session_sequence",
        ),
        Index("idx_recording_action_events_session_sequence", "recording_session_id", "sequence_no"),
        Index(
            "idx_recording_action_events_tenant_session_created_at",
            "tenant_id",
            "recording_session_id",
            "created_at",
        ),
    )


class SkillDraftRecord(Base):
    __tablename__ = "skill_drafts"

    skill_draft_id: Mapped[str] = mapped_column(primary_key=True)
    tenant_id: Mapped[str] = mapped_column(nullable=False, index=True)
    recording_session_id: Mapped[Optional[str]] = mapped_column(nullable=True, index=True)
    previous_skill_draft_id: Mapped[Optional[str]] = mapped_column(nullable=True)
    promoted_skill_id: Mapped[Optional[str]] = mapped_column(nullable=True)
    promoted_skill_version_id: Mapped[Optional[str]] = mapped_column(nullable=True)
    draft_key: Mapped[str] = mapped_column(nullable=False)
    draft_version: Mapped[str] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(nullable=False, index=True)
    name: Mapped[str] = mapped_column(nullable=False)
    intent_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    distillation_source_type: Mapped[str] = mapped_column(nullable=False)
    input_schema_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    output_schema_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    draft_definition_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    distillation_notes_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    execution_binding_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    derived_from_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_by: Mapped[Optional[str]] = mapped_column(nullable=True)
    updated_by: Mapped[Optional[str]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "draft_key",
            "draft_version",
            name="uq_skill_drafts_tenant_key_version",
        ),
        Index("idx_skill_drafts_tenant_created_at", "tenant_id", "created_at"),
        Index("idx_skill_drafts_tenant_status_created_at", "tenant_id", "status", "created_at"),
        Index("idx_skill_drafts_tenant_session_created_at", "tenant_id", "recording_session_id", "created_at"),
        Index("idx_skill_drafts_tenant_key_created_at", "tenant_id", "draft_key", "created_at"),
    )