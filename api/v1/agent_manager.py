from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional

router = APIRouter(prefix="/agents", tags=["Agent Management"])

# 模拟 Agent 注册表 (实际应从 LangGraph 或 DB 读取)
AGENT_REGISTRY = [
    {"id": "ag-001", "name": "客服助手", "type": "langgraph", "status": "running", "model": "ollama/llama3"},
    {"id": "ag-002", "name": "数据分析员", "type": "langgraph", "status": "stopped", "model": "azure/gpt-4"},
]

class AgentInfo(BaseModel):
    id: str
    name: str
    type: str
    status: str
    model: str

class AgentAction(BaseModel):
    action: str  # "start", "stop", "restart"

@router.get("/", response_model=List[AgentInfo])
def list_agents():
    """获取所有 Agent 状态"""
    return AGENT_REGISTRY

@router.post("/{agent_id}/control")
def control_agent(agent_id: str, action: AgentAction):
    """控制 Agent 生命周期 (启动/停止)"""
    agent = next((a for a in AGENT_REGISTRY if a["id"] == agent_id), None)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    # 模拟状态变更
    if action.action == "start":
        agent["status"] = "running"
    elif action.action == "stop":
        agent["status"] = "stopped"
    elif action.action == "restart":
        agent["status"] = "restarting" # 实际逻辑中稍后变回 running
        
    return {"message": f"Agent {agent['name']} {action.action}ed successfully", "new_status": agent["status"]}