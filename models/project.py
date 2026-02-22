"""
项目与环境管理模块
支持多环境、集成配置、资源隔离（ABAC 增强）
生成时间：2026-02-20
"""
from enum import Enum
from typing import Optional, List
from datetime import datetime
from sqlalchemy import String, Boolean, ForeignKey, Integer, Text, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB, ARRAY, TIMESTAMP
from .base import Base


class ProjectVisibility(str, Enum):
    PRIVATE = "private"
    INTERNAL = "internal"
    PUBLIC = "public"


class ProjectStatus(str, Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"


class Project(Base):
    """项目表 - 核心工作单元（ABAC 增强）"""
    __tablename__ = "projects"

    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False
    )
    slug: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="项目标识符"
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )
    visibility: Mapped[str] = mapped_column(
        String(20),
        default=ProjectVisibility.PRIVATE.value,
        nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(20),
        default=ProjectStatus.ACTIVE.value,
        nullable=False
    )
    settings: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        default=dict,
        comment="项目配置"
    )

    # ==================== ABAC 资源属性（新增）====================
    sensitivity: Mapped[str] = mapped_column(
        String(20),
        default="internal",
        nullable=False,
        index=True,
        comment="资源敏感度 (public, internal, confidential, restricted)"
    )
    owner_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="资源所有者（用于'仅所有者可访问'策略）"
    )
    tags: Mapped[list[str]] = mapped_column(
        ARRAY(String(50)),
        default=list,
        comment="资源标签，用于策略匹配"
    )
    classification: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="数据分类 (general, pii, financial, health)"
    )
    retention_days: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="数据保留天数（合规要求）"
    )

    # 关系
    organization: Mapped["Organization"] = relationship(
        "Organization",
        back_populates="projects"
    )
    environments: Mapped[List["Environment"]] = relationship(
        "Environment",
        back_populates="project",
        cascade="all, delete-orphan"
    )
    agents: Mapped[List["Agent"]] = relationship(
        "Agent",
        back_populates="project",
        cascade="all, delete-orphan"
    )
    conversations: Mapped[List["Conversation"]] = relationship(
        "Conversation",
        back_populates="project",
        cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint('organization_id', 'slug', name='uq_project_slug'),
        Index('idx_project_org', 'organization_id'),
        Index('idx_project_sensitivity', 'sensitivity'),
        Index('idx_project_owner', 'owner_id'),
        Index('idx_project_tags', 'tags', postgresql_using='gin'),
    )


class Environment(Base):
    """环境表 - 开发/测试/生产环境隔离"""
    __tablename__ = "environments"

    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="环境名称 (dev, staging, prod)"
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )
    variables: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        default=dict,
        comment="环境变量（加密存储）"
    )
    config: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        default=dict,
        comment="环境特定配置"
    )
    is_default: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False
    )

    # 关系
    project: Mapped["Project"] = relationship("Project", back_populates="environments")
    integrations: Mapped[List["Integration"]] = relationship(
        "Integration",
        back_populates="environment",
        cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint('project_id', 'name', name='uq_env_project_name'),
        Index('idx_env_project', 'project_id'),
    )


class Integration(Base):
    """集成表 - 第三方服务连接配置"""
    __tablename__ = "integrations"

    environment_id: Mapped[str] = mapped_column(
        ForeignKey("environments.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="集成名称"
    )
    provider: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="提供商 (openai, anthropic, azure, etc.)"
    )
    integration_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="类型 (llm, vector_store, tool, webhook)"
    )
    credentials: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="认证凭证（加密存储）"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False
    )
    health_status: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="健康状态 (healthy, degraded, unhealthy)"
    )
    last_health_check: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True
    )

    # 关系
    environment: Mapped["Environment"] = relationship("Environment", back_populates="integrations")

    __table_args__ = (
        Index('idx_integration_env', 'environment_id'),
        Index('idx_integration_provider', 'provider'),
    )