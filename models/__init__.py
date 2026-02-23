"""
AI-PaaS 数据模型注册表
统一导出所有模型类及数据库连接工具
"""
from .base import Base
from .auth import User, Organization, OrganizationMember, APIKey
from .project import Project, Environment, Integration
from .agent import Agent, Tool, WorkflowNode, WorkflowEdge
from .conversation import Conversation, Message, Feedback
from .prompt import PromptTemplate, TemplateVersion
from .billing import UsageRecord, Quota
from .audit import AuditLog, SystemSetting, FeatureFlag
from .abac import ABACPolicy, PolicyAssignment, PolicyEvaluationLog

# ==================== 数据库连接工具 ====================
# 从 database 模块导入会话管理工具（用于 API 依赖注入）
from .database import engine, SessionLocal, get_db, init_db

# ==================== 导出所有符号 ====================
__all__ = [
    # 基类
    "Base",
    # 数据库工具
    "engine",
    "SessionLocal",
    "get_db",
    "init_db",
    # Auth 模型
    "User",
    "Organization",
    "OrganizationMember",
    "APIKey",
    # Project 模型
    "Project",
    "Environment",
    "Integration",
    # Agent 模型
    "Agent",
    "Tool",
    "WorkflowNode",
    "WorkflowEdge",
    # Conversation 模型
    "Conversation",
    "Message",
    "Feedback",
    # Prompt 模型
    "PromptTemplate",
    "TemplateVersion",
    # Billing 模型
    "UsageRecord",
    "Quota",
    # Audit 模型
    "AuditLog",
    "SystemSetting",
    "FeatureFlag",
    # ABAC 模型
    "ABACPolicy",
    "PolicyAssignment",
    "PolicyEvaluationLog",
]