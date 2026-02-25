from sqlalchemy import Column, String, Text, Boolean, DateTime, ForeignKey, Float, Integer, Enum as SQLEnum
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum
from typing import List, TYPE_CHECKING

if TYPE_CHECKING:
    from .conversation import Conversation

from .base import Base

class AgentStatus(str, enum.Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DELETED = "deleted"

class Agent(Base):
    __tablename__ = "agents"

    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    
    owner_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    organization_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)
    
    model_name = Column(String(100), nullable=False)
    system_prompt = Column(Text, nullable=True)
    temperature = Column(Float, default=0.7)
    max_tokens = Column(Integer, default=2048)
    
    status = Column(String(20), default="draft") 
    sensitivity = Column(String(20), default="internal")
    requires_mfa = Column(Boolean, default=False)
    allowed_roles = Column(String(255), default="owner,admin")

    # 修复：添加缺失的反向关系定义
    # 使用字符串引用避免循环导入
    conversations = relationship("Conversation", back_populates="agent", cascade="all, delete-orphan", lazy="dynamic")
