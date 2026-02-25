from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import datetime
from enum import Enum

class AgentStatusEnum(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DELETED = "deleted"

# 基础 Schema (共用字段)
class AgentBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Agent name")
    description: Optional[str] = Field(None, description="Agent description")
    model_name: str = Field(..., description="LLM model name (e.g., qwen-max)")
    system_prompt: Optional[str] = Field(None, description="System prompt for the agent")
    temperature: float = Field(0.7, ge=0.0, le=2.0, description="Sampling temperature")
    max_tokens: int = Field(2048, ge=1, le=32000, description="Max tokens to generate")
    sensitivity: str = Field("internal", description="Resource sensitivity level")
    requires_mfa: bool = Field(False, description="Whether MFA is required to access")
    allowed_roles: Optional[List[str]] = Field(default=["owner", "admin"], description="Roles allowed to access")

# 创建时的 Schema
class AgentCreate(AgentBase):
    pass

# 更新时的 Schema (所有字段可选)
class AgentUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    model_name: Optional[str] = None
    system_prompt: Optional[str] = None
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(None, ge=1, le=32000)
    status: Optional[AgentStatusEnum] = None
    sensitivity: Optional[str] = None
    requires_mfa: Optional[bool] = None
    allowed_roles: Optional[List[str]] = None

# 响应 Schema (包含数据库生成的字段)
class AgentResponse(AgentBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    owner_id: str
    organization_id: str
    status: str
    created_at: datetime
    updated_at: datetime
