"""
会话与消息管理模块 (Integrated with Prompt Engineering)
支持多轮对话、消息历史、反馈收集（ABAC 增强）及 Prompt 模板版本控制
生成时间：2026-02-25
"""
from enum import Enum
from typing import Optional, List, Dict, Any, TYPE_CHECKING
from datetime import datetime
from sqlalchemy import String, Boolean, ForeignKey, Integer, Text, Index, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB, ARRAY, UUID as PG_UUID
from sqlalchemy.sql import func

from .base import Base

# 使用 TYPE_CHECKING 避免循环导入，仅在类型检查时引入 PromptTemplate
if TYPE_CHECKING:
    from .prompt import PromptTemplate
    from .agent import Agent
    from .project import Project
    from .user import User


from uuid import UUID

class MessageRole(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class MessageStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Conversation(Base):
    """会话表 - 对话会话（ABAC 增强 + Prompt 快照）"""
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(
        String(36), 
        primary_key=True, 
        default=lambda: str(__import__('uuid').uuid4())
    )

    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    agent_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("agents.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    user_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    
    # [新增] 关联 Prompt 模板快照
    # 指向 models/prompt.py 中定义的 prompt_templates 表
    prompt_template_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("prompt_templates.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="创建会话时使用的 Prompt 模板 ID (快照)"
    )

    title: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="会话标题"
    )
    status: Mapped[str] = mapped_column(
        String(20),
        default="active",
        nullable=False
    )
    metadata_: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        default=dict,
        comment="会话元数据"
    )
    message_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False
    )

    # ==================== ABAC 资源属性 ====================
    sensitivity: Mapped[str] = mapped_column(
        String(20),
        default="internal",
        nullable=False,
        index=True,
        comment="资源敏感度"
    )
    owner_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="会话所有者"
    )
    tags: Mapped[list[str]] = mapped_column(
        ARRAY(String(50)),
        default=list,
        comment="会话标签"
    )
    is_encrypted: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        comment="是否加密存储"
    )

    # ==================== 关系定义 ====================
    # 注意：确保 models/prompt.py 中的 PromptTemplate 类添加了 back_populates="conversations"
    prompt_template: Mapped[Optional["PromptTemplate"]] = relationship(
        "PromptTemplate", 
        back_populates="conversations"
    )
    
    # 确保 models/project.py, models/agent.py, models/user.py 中也有对应的 back_populates
    project: Mapped["Project"] = relationship("Project", back_populates="conversations")
    agent: Mapped["Agent"] = relationship("Agent", back_populates="conversations")
    # user 关系如果 User 模型中没有定义 conversations，可能会报错，若报错请移除 back_populates
    user: Mapped[Optional["User"]] = relationship("User", foreign_keys=[user_id], viewonly=True) 
    
    messages: Mapped[List["Message"]] = relationship(
        "Message",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.created_at"
    )
    feedbacks: Mapped[List["Feedback"]] = relationship(
        "Feedback",
        back_populates="conversation",
        cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index('idx_conversation_project', 'project_id'),
        Index('idx_conversation_user', 'user_id'),
        Index('idx_conversation_status', 'status'),
        Index('idx_conversation_sensitivity', 'sensitivity'),
        Index('idx_conversation_owner', 'owner_id'),
        Index('idx_conversation_prompt_template', 'prompt_template_id'),
    )


class Message(Base):
    """消息表 - 对话消息"""
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(
        String(36), 
        primary_key=True, 
        default=lambda: str(__import__('uuid').uuid4())
    )

    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False
    )
    content: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )
    attachments: Mapped[Optional[List[dict]]] = mapped_column(
        JSONB,
        default=list,
        comment="附件列表"
    )
    tool_calls: Mapped[Optional[List[dict]]] = mapped_column(
        JSONB,
        default=list,
        comment="工具调用记录"
    )
    tool_call_id: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="关联的工具调用 ID"
    )
    status: Mapped[str] = mapped_column(
        String(20),
        default=MessageStatus.COMPLETED.value,
        nullable=False
    )
    token_count: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Token 数量"
    )
    latency_ms: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="响应延迟（毫秒）"
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="错误信息"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        server_default=func.now(), 
        nullable=False
    )

    # 关系
    conversation: Mapped["Conversation"] = relationship("Conversation", back_populates="messages")

    __table_args__ = (
        Index('idx_message_conversation', 'conversation_id'),
        Index('idx_message_role', 'role'),
        Index('idx_message_created', 'created_at'),
    )


class Feedback(Base):
    """反馈表 - 用户反馈收集"""
    __tablename__ = "feedbacks"

    id: Mapped[str] = mapped_column(
        String(36), 
        primary_key=True, 
        default=lambda: str(__import__('uuid').uuid4())
    )

    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    message_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("messages.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    user_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )
    rating: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="评分 (1-5)"
    )
    comment: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )
    category: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="反馈类别"
    )
    is_reviewed: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False
    )
    review_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        server_default=func.now(), 
        nullable=False
    )

    # 关系
    conversation: Mapped["Conversation"] = relationship("Conversation", back_populates="feedbacks")

    __table_args__ = (
        Index('idx_feedback_conversation', 'conversation_id'),
        Index('idx_feedback_rating', 'rating'),
    )