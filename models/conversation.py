"""
会话与消息管理模块
支持多轮对话、消息历史、反馈收集（ABAC 增强）
生成时间：2026-02-20
"""
from enum import Enum
from typing import Optional, List
from datetime import datetime
from sqlalchemy import String, Boolean, ForeignKey, Integer, Text, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB, ARRAY, TIMESTAMP
from .base import Base


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
    """会话表 - 对话会话（ABAC 增强）"""
    __tablename__ = "conversations"

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

    # ==================== ABAC 资源属性（新增）====================
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

    # 关系
    project: Mapped["Project"] = relationship("Project", back_populates="conversations")
    agent: Mapped["Agent"] = relationship("Agent", back_populates="conversations")
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
    )


class Message(Base):
    """消息表 - 对话消息"""
    __tablename__ = "messages"

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

    # 关系
    conversation: Mapped["Conversation"] = relationship("Conversation", back_populates="feedbacks")

    __table_args__ = (
        Index('idx_feedback_conversation', 'conversation_id'),
        Index('idx_feedback_rating', 'rating'),
    )