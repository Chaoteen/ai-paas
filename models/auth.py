"""
用户管理与认证模块
支持多租户、RBAC+ABAC 混合权限、API 密钥管理
生成时间：2026-02-20
"""
from enum import Enum
from typing import Optional, List
from datetime import datetime
from sqlalchemy import String, Boolean, ForeignKey, Index, Text, DateTime, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB, ARRAY, TIMESTAMP
from .base import Base


class UserRole(str, Enum):
    """用户角色枚举"""
    SUPER_ADMIN = "super_admin"
    ORG_ADMIN = "org_admin"
    TEAM_LEAD = "team_lead"
    DEVELOPER = "developer"
    VIEWER = "viewer"
    SERVICE = "service"


class UserStatus(str, Enum):
    """用户状态枚举"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    PENDING_VERIFICATION = "pending_verification"


class User(Base):
    """用户表 - 核心用户信息（ABAC 增强）"""
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
        comment="用户邮箱（登录凭证）"
    )
    username: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        index=True,
        nullable=False,
        comment="用户名"
    )
    password_hash: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="密码哈希（OAuth 用户为空）"
    )
    full_name: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True
    )
    avatar_url: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(50),
        default=UserStatus.PENDING_VERIFICATION.value,
        nullable=False
    )
    role: Mapped[str] = mapped_column(
        String(50),
        default=UserRole.DEVELOPER.value,
        nullable=False
    )
    oauth_provider: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="OAuth 提供商 (github, google, microsoft)"
    )
    oauth_sub: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="OAuth 提供商的用户 ID"
    )
    metadata_: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        default=dict,
        nullable=True,
        comment="扩展元数据"
    )

    # ==================== ABAC 主体属性（新增）====================
    department: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        index=True,
        comment="所属部门 (engineering, product, sales, etc.)"
    )
    level: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        index=True,
        comment="职级 (L1-L10, 用于权限分级)"
    )
    auth_level: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        default="basic",
        comment="认证级别 (basic, mfa_enabled, hardware_key)"
    )
    abac_attributes: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        default=dict,
        nullable=True,
        comment="ABAC 扩展属性，支持自定义主体属性"
    )

    # 关系
    api_keys: Mapped[List["APIKey"]] = relationship(
        "APIKey",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    
    # ✅ 修复：明确指定 foreign_keys 解决歧义
    organizations: Mapped[List["OrganizationMember"]] = relationship(
        "OrganizationMember",
        foreign_keys="OrganizationMember.user_id",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    
    audit_logs: Mapped[List["AuditLog"]] = relationship(
        "AuditLog",
        back_populates="actor",
        cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index('idx_users_status', 'status'),
        Index('idx_users_oauth', 'oauth_provider', 'oauth_sub'),
        Index('idx_users_department', 'department'),
        Index('idx_users_level', 'level'),
        Index('idx_users_auth_level', 'auth_level'),
        Index('idx_users_abac', 'abac_attributes', postgresql_using='gin'),
    )


class Organization(Base):
    """组织表 - 多租户支持（ABAC 增强）"""
    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="组织名称"
    )
    slug: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        index=True,
        nullable=False,
        comment="组织标识符（URL 友好）"
    )
    owner_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="组织所有者"
    )
    plan: Mapped[str] = mapped_column(
        String(50),
        default="free",
        comment="订阅计划 (free, pro, enterprise)"
    )
    settings: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        default=dict,
        comment="组织配置"
    )

    # ==================== ABAC 组织属性（新增）====================
    sensitivity_default: Mapped[str] = mapped_column(
        String(20),
        default="internal",
        comment="默认资源敏感度 (public, internal, confidential, restricted)"
    )
    compliance_tags: Mapped[list[str]] = mapped_column(
        ARRAY(String(50)),
        default=list,
        comment="合规标签 (gdpr, hipaa, soc2, etc.)"
    )
    allowed_locations: Mapped[Optional[list[str]]] = mapped_column(
        ARRAY(String(10)),
        nullable=True,
        comment="允许的地理位置 (CN, US, EU, etc.)"
    )
    data_residency: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="数据驻留要求 (cn-north, us-east, eu-west)"
    )

    # 关系
    members: Mapped[List["OrganizationMember"]] = relationship(
        "OrganizationMember",
        back_populates="organization",
        cascade="all, delete-orphan"
    )
    projects: Mapped[List["Project"]] = relationship(
        "Project",
        back_populates="organization",
        cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index('idx_org_slug', 'slug'),
        Index('idx_org_sensitivity', 'sensitivity_default'),
        Index('idx_org_compliance', 'compliance_tags', postgresql_using='gin'),
    )


class OrganizationMember(Base):
    """组织成员表 - 用户与组织的多对多关系"""
    __tablename__ = "organization_members"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False
    )
    role: Mapped[str] = mapped_column(
        String(50),
        default=UserRole.DEVELOPER.value,
        nullable=False
    )
    invited_by: Mapped[Optional[str]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )
    invited_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    joined_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    # ==================== 关系定义（已修复外键歧义）====================
    user: Mapped["User"] = relationship(
        "User",
        foreign_keys=[user_id],
        back_populates="organizations"
    )
    
    organization: Mapped["Organization"] = relationship(
        "Organization",
        back_populates="members"
    )
    
    # 可选：添加邀请人关系
    inviter: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[invited_by],
        primaryjoin="OrganizationMember.invited_by == User.id"
    )

    __table_args__ = (
        UniqueConstraint('user_id', 'organization_id', name='uq_org_member'),
        Index('idx_org_member_user', 'user_id'),
        Index('idx_org_member_org', 'organization_id'),
    )


class APIKey(Base):
    """API 密钥表 - 用于服务认证"""
    __tablename__ = "api_keys"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="密钥名称（用户自定义）"
    )
    key_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="密钥哈希（存储 bcrypt 哈希）"
    )
    key_prefix: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        comment="密钥前缀（用于识别，如 sk-abc123）"
    )
    scopes: Mapped[List[str]] = mapped_column(
        ARRAY(String(50)),
        default=list,
        comment="权限范围 (read, write, admin)"
    )
    allowed_ips: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String(45)),
        nullable=True,
        comment="允许访问的 IP 列表"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False
    )
    last_used_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="过期时间（None 表示永不过期）"
    )

    # 关系
    user: Mapped["User"] = relationship("User", back_populates="api_keys")

    __table_args__ = (
        Index('idx_api_key_prefix', 'key_prefix'),
        Index('idx_api_key_active', 'is_active'),
    )