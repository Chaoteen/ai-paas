"""
提示词模板管理模块
支持版本控制、变量替换、模板库
"""
from typing import Optional, List
from datetime import datetime
from enum import Enum
from sqlalchemy import String, Boolean, ForeignKey, Integer, Text, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from .base import Base


class TemplateVisibility(str, Enum):
    PRIVATE = "private"
    TEAM = "team"
    PUBLIC = "public"


class PromptTemplate(Base):
    """提示词模板表"""
    __tablename__ = "prompt_templates"

    project_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=True,
        index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    template: Mapped[str] = mapped_column(Text, nullable=False)
    variables: Mapped[Optional[list[dict]]] = mapped_column(JSONB, default=list)
    category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    tags: Mapped[list[str]] = mapped_column(ARRAY(String(50)), default=list)
    visibility: Mapped[str] = mapped_column(String(20), default=TemplateVisibility.PRIVATE.value, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_latest: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    usage_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    project: Mapped[Optional["Project"]] = relationship("Project")

    __table_args__ = (
        Index('idx_template_project', 'project_id'),
        Index('idx_template_category', 'category'),
        Index('idx_template_tags', 'tags', postgresql_using='gin'),
    )


class TemplateVersion(Base):
    """模板版本历史表"""
    __tablename__ = "template_versions"

    template_id: Mapped[str] = mapped_column(ForeignKey("prompt_templates.id", ondelete="CASCADE"), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    template: Mapped[str] = mapped_column(Text, nullable=False)
    variables: Mapped[Optional[list[dict]]] = mapped_column(JSONB, default=list)
    change_summary: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    changed_by: Mapped[Optional[str]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    __table_args__ = (
        UniqueConstraint('template_id', 'version', name='uq_template_version'),
        Index('idx_template_version', 'template_id', 'version'),
    )
