"""
使用量计量与配额管理模块
支持多指标追踪、配额限制、计费
"""
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Boolean,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class UsageMetric(str, Enum):
    TOKENS_INPUT = "tokens_input"
    TOKENS_OUTPUT = "tokens_output"
    API_CALLS = "api_calls"
    AGENT_RUNS = "agent_runs"
    STORAGE_BYTES = "storage_bytes"
    COMPUTE_SECONDS = "compute_seconds"


class UsageRecord(Base):
    """使用量记录表 - 按小时聚合"""
    __tablename__ = "usage_records"

    organization_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    project_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    user_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    agent_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    period_start: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
    )
    period_end: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
    )
    metric: Mapped[str] = mapped_column(String(50), nullable=False)
    quantity: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    unit_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 6), nullable=True)
    total_cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    metadata_: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)

    __table_args__ = (
        Index("idx_usage_org_period", "organization_id", "period_start"),
        Index("idx_usage_metric", "metric"),
        Index("idx_usage_project", "project_id"),
    )


class Quota(Base):
    """配额表 - 资源限制"""
    __tablename__ = "quotas"

    organization_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    project_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=True,
    )
    metric: Mapped[str] = mapped_column(String(50), nullable=False)
    limit: Mapped[int] = mapped_column(BigInteger, nullable=False)
    used: Mapped[int] = mapped_column(BigInteger, default=0)
    period: Mapped[str] = mapped_column(String(20), default="monthly")
    period_start: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    action_on_exceed: Mapped[str] = mapped_column(String(20), default="block")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "project_id",
            "metric",
            "period_start",
            name="uq_quota",
        ),
        Index("idx_quota_org", "organization_id"),
    )