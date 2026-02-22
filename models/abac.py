"""
ABAC 属性基访问控制策略模块
Attribute-Based Access Control - 比 RBAC 更细粒度的权限模型
生成时间：2026-02-20
"""
from typing import Optional, List
from datetime import datetime, timezone
from enum import Enum
from sqlalchemy import String, Boolean, ForeignKey, Integer, Text, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB, ARRAY, TIMESTAMP
from .base import Base


class PolicyEffect(str, Enum):
    """策略效果"""
    ALLOW = "allow"
    DENY = "deny"


class TargetType(str, Enum):
    """策略绑定目标类型"""
    ORGANIZATION = "organization"
    PROJECT = "project"
    USER = "user"
    ROLE = "role"
    ALL = "all"


class ABACPolicy(Base):
    """
    ABAC 策略表 - 核心权限规则定义
    
    一条策略 = 当 (主体条件 + 环境条件) 满足时，对 (资源) 执行 (动作) 返回 (效果)
    """
    __tablename__ = "abac_policies"
    
    # 策略基本信息
    name: Mapped[str] = mapped_column(String(200), nullable=False, comment="策略名称")
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="策略详细描述")
    effect: Mapped[str] = mapped_column(String(10), default=PolicyEffect.ALLOW.value, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="优先级")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    # 主体条件 (Subject)
    subject_conditions: Mapped[Optional[dict]] = mapped_column(
        JSONB, default=dict, nullable=True,
        comment="主体属性条件 {roles, departments, levels, auth_levels, user_ids}"
    )
    
    # 资源条件 (Resource)
    resource_conditions: Mapped[Optional[dict]] = mapped_column(
        JSONB, default=dict, nullable=True,
        comment="资源属性条件 {resource_types, sensitivities, owners, tags}"
    )
    
    # 环境条件 (Environment)
    environment_conditions: Mapped[Optional[dict]] = mapped_column(
        JSONB, default=dict, nullable=True,
        comment="环境属性条件 {time_range, ip_whitelist, locations}"
    )
    
    # 动作 (Action)
    actions: Mapped[List[str]] = mapped_column(ARRAY(String(50)), default=list, comment="允许/拒绝的动作列表")
    
    # 关系
    assignments: Mapped[List["PolicyAssignment"]] = relationship(
        "PolicyAssignment", back_populates="policy", cascade="all, delete-orphan"
    )
    
    __table_args__ = (
        Index('idx_policy_effect', 'effect'),
        Index('idx_policy_priority', 'priority'),
        Index('idx_policy_active', 'is_active'),
        Index('idx_policy_subject', 'subject_conditions', postgresql_using='gin'),
        Index('idx_policy_resource', 'resource_conditions', postgresql_using='gin'),
    )


class PolicyAssignment(Base):
    """策略分配表 - 将策略绑定到具体目标"""
    __tablename__ = "policy_assignments"
    
    policy_id: Mapped[str] = mapped_column(
        ForeignKey("abac_policies.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    target_type: Mapped[str] = mapped_column(String(50), nullable=False)
    target_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    extra_conditions: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict, nullable=True)
    
    policy: Mapped["ABACPolicy"] = relationship("ABACPolicy", back_populates="assignments")
    
    __table_args__ = (
        UniqueConstraint('policy_id', 'target_type', 'target_id', name='uq_policy_assignment'),
        Index('idx_assignment_target', 'target_type', 'target_id'),
    )


class PolicyEvaluationLog(Base):
    """策略评估日志表 - 用于审计和调试"""
    __tablename__ = "policy_evaluation_logs"
    
    subject_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    subject_attributes: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    resource_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    resource_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    resource_attributes: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    action: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    decision: Mapped[str] = mapped_column(String(10), nullable=False)
    matched_policies: Mapped[List[str]] = mapped_column(ARRAY(String(100)), default=list)
    deny_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45))
    user_agent: Mapped[Optional[str]] = mapped_column(String(500))
    request_time: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    
    __table_args__ = (
        Index('idx_policy_log_time', 'request_time'),
        Index('idx_policy_log_decision', 'decision'),
    )