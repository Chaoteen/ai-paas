"""
提示词模板管理模块
支持版本控制、变量替换、模板库
生成时间：2026-02-25
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
from sqlalchemy import String, Boolean, ForeignKey, Integer, Text, Index, UniqueConstraint, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB, ARRAY, UUID as PG_UUID
from sqlalchemy.sql import func

from .base import Base


from uuid import UUID

class TemplateVisibility(str, Enum):
    PRIVATE = "private"
    TEAM = "team"
    PUBLIC = "public"


class PromptTemplate(Base):
    """提示词模板表"""
    __tablename__ = "prompt_templates"

    # [关键修复] 添加主键 ID，类型必须与 conversation.py 中的外键类型一致 (String(36))
    id: Mapped[str] = mapped_column(
        String(36), 
        primary_key=True, 
        default=lambda: str(__import__('uuid').uuid4())
    )

    project_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=True,
        index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    template: Mapped[str] = mapped_column(Text, nullable=False)
    
    # 变量定义 Schema (JSONB)，用于前端表单生成或校验
    variables: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(JSONB, default=list)
    
    category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    tags: Mapped[List[str]] = mapped_column(ARRAY(String(50)), default=list)
    
    visibility: Mapped[str] = mapped_column(
        String(20), 
        default=TemplateVisibility.PRIVATE.value, 
        nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_latest: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    usage_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        server_default=func.now(), 
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        server_default=func.now(), 
        onupdate=func.now(), 
        nullable=False
    )

    # ==================== 关系定义 ====================
    
    # 1. 与 Project 的关系
    # 注意：如果 models/project.py 中没有定义 back_populates="prompt_templates"，
    # 请将 back_populates 参数移除，或改为 viewonly=True 以避免报错。
    # 推荐先尝试带 back_populates，如果报错再改。
    project: Mapped[Optional["Project"]] = relationship(
        "Project", 
        back_populates="prompt_templates" 
    )
    
    # 2. 与 Conversation 的关系 (双向绑定)
    # 这里的属性名 'conversations' 对应 conversation.py 中的 back_populates="prompt_template"
    conversations: Mapped[List["Conversation"]] = relationship(
        "Conversation", 
        back_populates="prompt_template",
        # 不建议加 cascade="all, delete-orphan"，因为删除模板不应删除历史会话记录
    )

    # 3. 与 TemplateVersion 的关系 (可选，方便查询历史)
    versions: Mapped[List["TemplateVersion"]] = relationship(
        "TemplateVersion",
        back_populates="template",
        cascade="all, delete-orphan",
        order_by="TemplateVersion.version"
    )

    __table_args__ = (
        Index('idx_template_project', 'project_id'),
        Index('idx_template_category', 'category'),
        Index('idx_template_tags', 'tags', postgresql_using='gin'),
        Index('idx_template_visibility', 'visibility'),
        # 复合索引：快速查找某个项目下的最新模板
        Index('idx_template_project_latest', 'project_id', 'is_latest'),
    )


class TemplateVersion(Base):
    """模板版本历史表"""
    __tablename__ = "template_versions"

    id: Mapped[str] = mapped_column(
        String(36), 
        primary_key=True, 
        default=lambda: str(__import__('uuid').uuid4())
    )

    template_id: Mapped[str] = mapped_column(
        ForeignKey("prompt_templates.id", ondelete="CASCADE"), 
        nullable=False, 
        index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    template: Mapped[str] = mapped_column(Text, nullable=False)
    variables: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(JSONB, default=list)
    change_summary: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    changed_by: Mapped[Optional[str]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), 
        nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        server_default=func.now(), 
        nullable=False
    )

    # ==================== 关系定义 ====================
    template: Mapped["PromptTemplate"] = relationship(
        "PromptTemplate", 
        back_populates="versions"
    )

    __table_args__ = (
        UniqueConstraint('template_id', 'version', name='uq_template_version'),
        Index('idx_template_version_lookup', 'template_id', 'version'),
    )