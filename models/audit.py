"""
审计日志与系统配置模块（ABAC 增强）
生成时间：2026-02-20
"""
from enum import Enum
from typing import Optional, List
from datetime import datetime
from sqlalchemy import String, Boolean, ForeignKey, Text, Integer, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB, ARRAY, TIMESTAMP
from .base import Base


class AuditAction(str, Enum):
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    LOGIN = "login"
    LOGOUT = "logout"
    API_CALL = "api_call"
    DEPLOY = "deploy"
    CONFIG_CHANGE = "config_change"


class AuditLog(Base):
    """审计日志表（ABAC 增强）"""
    __tablename__ = "audit_logs"

    actor_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    actor_type: Mapped[str] = mapped_column(
        String(20),
        default="user",
        comment="主体类型 (user, api_key, system)"
    )
    action: Mapped[str] = mapped_column(
        String(50),
        nullable=False
    )
    resource_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="资源类型"
    )
    resource_id: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        index=True
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )
    request_data: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="请求数据快照"
    )
    response_data: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="响应数据快照"
    )
    ip_address: Mapped[Optional[str]] = mapped_column(
        String(45),
        nullable=True
    )
    user_agent: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(20),
        default="success",
        comment="操作状态"
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )

    # ==================== ABAC 审计增强（新增）====================
    policy_decision: Mapped[Optional[str]] = mapped_column(
        String(10),
        nullable=True,
        comment="OPA 策略决策结果 (allow/deny)"
    )
    matched_policy_ids: Mapped[Optional[list[str]]] = mapped_column(
        ARRAY(String(100)),
        nullable=True,
        comment="匹配到的策略 ID 列表"
    )
    policy_evaluation_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("policy_evaluation_logs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="关联的策略评估日志 ID"
    )

    # 关系
    actor: Mapped[Optional["User"]] = relationship("User", back_populates="audit_logs")

    __table_args__ = (
        Index('idx_audit_actor', 'actor_id'),
        Index('idx_audit_action', 'action'),
        Index('idx_audit_resource', 'resource_type', 'resource_id'),
        Index('idx_audit_created', 'created_at'),
        Index('idx_audit_policy_decision', 'policy_decision'),
        Index('idx_audit_policy_eval', 'policy_evaluation_id'),
    )


class SystemSetting(Base):
    """系统配置表"""
    __tablename__ = "system_settings"

    key: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        primary_key=True,
        comment="配置键"
    )
    value: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="配置值"
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )
    is_sensitive: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        comment="是否敏感配置"
    )


class FeatureFlag(Base):
    """功能开关表"""
    __tablename__ = "feature_flags"

    name: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        primary_key=True
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )
    is_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False
    )
    target_orgs: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String(100)),
        default=list,
        comment="目标组织列表"
    )
    target_users: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String(100)),
        default=list,
        comment="目标用户列表"
    )
    rollout_percentage: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="灰度发布百分比 (0-100)"
    )
    metadata_: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        default=dict
    )