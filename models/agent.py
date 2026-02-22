"""
Agent 与工作流引擎模块
支持 LangGraph、PromptFlow 工作流定义（ABAC 增强）
"""
from enum import Enum
from typing import Optional, List
from datetime import datetime
from sqlalchemy import String, Boolean, ForeignKey, Integer, Text, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB, ARRAY, TIMESTAMP
from .base import Base


class AgentType(str, Enum):
    CHAT = "chat"
    TASK = "task"
    WORKFLOW = "workflow"
    ASSISTANT = "assistant"


class AgentStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    INACTIVE = "inactive"
    DEPRECATED = "deprecated"


class Agent(Base):
    """Agent 表 - AI 智能体定义（ABAC 增强）"""
    __tablename__ = "agents"

    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    agent_type: Mapped[str] = mapped_column(String(50), default=AgentType.CHAT.value, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default=AgentStatus.DRAFT.value, nullable=False)
    model_provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    model_config: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    system_prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    workflow_definition: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    workflow_engine: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    enabled_tools: Mapped[List[str]] = mapped_column(ARRAY(String(100)), default=list)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    # ABAC 资源属性
    sensitivity: Mapped[str] = mapped_column(String(20), default="internal", nullable=False, index=True)
    owner_id: Mapped[Optional[str]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    tags: Mapped[list[str]] = mapped_column(ARRAY(String(50)), default=list)
    allowed_roles: Mapped[Optional[list[str]]] = mapped_column(ARRAY(String(50)), nullable=True)
    requires_mfa: Mapped[bool] = mapped_column(Boolean, default=False)

    project: Mapped["Project"] = relationship("Project", back_populates="agents")
    tools: Mapped[List["Tool"]] = relationship("Tool", back_populates="agent", cascade="all, delete-orphan")
    conversations: Mapped[List["Conversation"]] = relationship("Conversation", back_populates="agent", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint('project_id', 'slug', name='uq_agent_slug'),
        Index('idx_agent_project', 'project_id'),
        Index('idx_agent_status', 'status'),
        Index('idx_agent_sensitivity', 'sensitivity'),
        Index('idx_agent_owner', 'owner_id'),
        Index('idx_agent_tags', 'tags', postgresql_using='gin'),
    )


class Tool(Base):
    """工具表 - Agent 可调用的功能"""
    __tablename__ = "tools"

    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tool_type: Mapped[str] = mapped_column(String(50), nullable=False)
    function_schema: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    endpoint: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    auth_config: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    agent: Mapped["Agent"] = relationship("Agent", back_populates="tools")

    __table_args__ = (
        Index('idx_tool_agent', 'agent_id'),
    )


class WorkflowNode(Base):
    """工作流节点表 - LangGraph 节点定义"""
    __tablename__ = "workflow_nodes"

    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True)
    node_id: Mapped[str] = mapped_column(String(100), nullable=False)
    node_type: Mapped[str] = mapped_column(String(50), nullable=False)
    config: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    __table_args__ = (
        UniqueConstraint('agent_id', 'node_id', name='uq_workflow_node'),
        Index('idx_workflow_node_agent', 'agent_id'),
    )


class WorkflowEdge(Base):
    """工作流边表 - 节点间连接"""
    __tablename__ = "workflow_edges"

    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), nullable=False)
    source_node: Mapped[str] = mapped_column(String(100), nullable=False)
    target_node: Mapped[str] = mapped_column(String(100), nullable=False)
    condition: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    __table_args__ = (
        Index('idx_workflow_edge_agent', 'agent_id'),
    )
