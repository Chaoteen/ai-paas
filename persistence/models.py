from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import DateTime, Index, Integer, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
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
    - future outbox relay and retry orchestration
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

    In current scope, only task.queued is supported.
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
    publish_attempts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
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