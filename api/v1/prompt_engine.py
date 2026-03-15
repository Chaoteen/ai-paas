from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import uuid
import datetime

# 初始化路由
router = APIRouter(prefix="/prompts", tags=["Prompt Engineering"])

# --- 模拟数据库 (开发阶段用，正式请替换为 SQLAlchemy) ---
# 结构: { id: { data } }
PROMPT_DB = {}

# --- 数据模型 ---
class PromptCreate(BaseModel):
    name: str
    description: str
    content: str
    engine_type: str = "flowise"  # 选项: "flowise", "promptflow", "langgraph"
    config: Dict[str, Any] = {}  # 存储 Flowise ID 或 PF Flow Name 等配置

class PromptUpdate(BaseModel):
    name: Optional[str] = None
    content: Optional[str] = None
    config: Optional[Dict[str, Any]] = None

class PromptResponse(BaseModel):
    id: str
    name: str
    description: str
    engine_type: str
    created_at: str
    status: str

class RunRequest(BaseModel):
    user_input: str
    session_id: Optional[str] = None

class RunResponse(BaseModel):
    output: str
    engine_used: str
    latency_ms: int

# --- 接口实现 ---

@router.post("/", response_model=PromptResponse, status_code=status.HTTP_201_CREATED)
def create_prompt(prompt: PromptCreate):
    """创建新的提示词工程任务"""
    pid = str(uuid.uuid4())
    now = datetime.datetime.now().isoformat()
    
    record = {
        "id": pid,
        **prompt.dict(),
        "created_at": now,
        "status": "active"
    }
    PROMPT_DB[pid] = record
    
    return PromptResponse(**record)

@router.get("/", response_model=List[PromptResponse])
def list_prompts():
    """获取所有提示词列表"""
    return [PromptResponse(**p) for p in PROMPT_DB.values()]

@router.get("/{prompt_id}", response_model=PromptResponse)
def get_prompt(prompt_id: str):
    """获取单个提示词详情"""
    if prompt_id not in PROMPT_DB:
        raise HTTPException(status_code=404, detail="Prompt not found")
    return PromptResponse(**PROMPT_DB[prompt_id])

@router.post("/{prompt_id}/run", response_model=RunResponse)
def run_prompt(prompt_id: str, request: RunRequest):
    """
    统一执行入口：
    1. 查找 Prompt 配置
    2. 根据 engine_type 路由到不同引擎 (Flowise / PromptFlow / LangGraph)
    3. 返回结果
    """
    if prompt_id not in PROMPT_DB:
        raise HTTPException(status_code=404, detail="Prompt not found")
    
    prompt_config = PROMPT_DB[prompt_id]
    engine = prompt_config["engine_type"]
    
    import time
    start_time = time.time()
    result_output = ""
    
    # --- 路由逻辑 ---
    if engine == "flowise":
        # TODO: 调用现有的 flowise_bridge 逻辑
        # from api.v1.flowise_bridge import execute_flowise
        # result_output = await execute_flowise(prompt_config["config"], request.user_input)
        result_output = f"[Flowise] 成功执行 '{prompt_config['name']}': 收到输入 '{request.user_input}'"
        
    elif engine == "promptflow":
        # TODO: 调用 services/promptflow_client.py
        # from services.promptflow_client import run_flow
        # result_output = await run_flow(prompt_config["config"]["flow_name"], request.user_input)
        result_output = f"[PromptFlow] 复杂逻辑执行完毕: '{prompt_config['name']}' 处理了 '{request.user_input}'"
        
    elif engine == "langgraph":
        # TODO: 调用 services/langgraph_client.py
        result_output = f"[LangGraph] Agent '{prompt_config['name']}' 状态机运行完成。"
        
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported engine: {engine}")
    
    latency = int((time.time() - start_time) * 1000)
    
    return RunResponse(output=result_output, engine_used=engine, latency_ms=latency)

@router.delete("/{prompt_id}")
def delete_prompt(prompt_id: str):
    if prompt_id not in PROMPT_DB:
        raise HTTPException(status_code=404, detail="Prompt not found")
    del PROMPT_DB[prompt_id]
    return {"message": "Deleted successfully"}