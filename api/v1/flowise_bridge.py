from fastapi import APIRouter, HTTPException, Header, Depends, status
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import httpx
import os
import uuid
from datetime import datetime

# 【新增】导入数据库相关
from sqlalchemy.orm import Session
from models.database import get_db  # 确保这个路径正确，指向您的 get_db 函数
from models.conversation import Conversation,Message  # 确保路径正确
from models.project import Project           # 确保路径正确

router = APIRouter(prefix="/flowise", tags=["Flowise Integration"])

# 配置项
PF_BASE_URL = os.getenv("PROMPTFLOW_SERVICE_URL", "http://127.0.0.1:8080/score")
PROMPTFLOW_ENDPOINT = PF_BASE_URL

# 【临时修改】为了测试，暂时跳过 API Key 验证，或者您可以改为验证 Bearer Token
# 原代码：EXPECTED_API_KEY = os.getenv("FLOWISE_GATEWAY_KEY", "sk-test-flowise-integration-key")
# async def verify_api_key(...): ... 
# 我们暂时注释掉验证，让请求直接通过，方便调试落库逻辑
# 如果后续需要恢复，请取消注释并调整 Flowise 的 Header
async def verify_api_key(x_api_key: Optional[str] = Header(None)):
    return "debug-key" 

class FlowiseRequest(BaseModel):
    question: str
    chatId: Optional[str] = None # 【新增】接收 chatId 用于关联会话
    history: Optional[List[Dict[str, str]]] = []
    override_config: Optional[Dict[str, Any]] = {}

class FlowiseResponse(BaseModel):
    text: str
    question: str
    history: Optional[List[Dict[str, str]]] = []
    sessionId: Optional[str] = None

@router.post("/execute", response_model=FlowiseResponse)
async def execute_prompt(
    request: FlowiseRequest,
    api_key: str = Depends(verify_api_key),
    db: Session = Depends(get_db)  # 【新增】注入数据库会话
):
    """
    Flowise 专用接口：接收用户问题 -> 调用 PromptFlow -> 保存对话到 DB -> 返回结果
    """
    print(f"[Flowise Bridge] 收到请求: {request.question}")
    
    # 默认用户 ID (TODO: 未来从 JWT Token 中解析真实用户 ID)
    DEFAULT_USER_ID = "f92cc300-90cc-467c-a28e-60f2b87254bb" 
    user_id = DEFAULT_USER_ID
    owner_id = user_id

    try:
        # 1. 获取或创建项目 (取第一个项目作为默认)
        project = db.query(Project).first()
        if not project:
            # 如果没项目，报错或创建一个默认的 (这里选择报错，防止数据孤儿)
            raise HTTPException(status_code=500, detail="No project found in database. Please create a project first.")
        project_id = project.id

        # 2. 创建会话 (Conversation)
        # 如果 request.chatId 存在，可以尝试用它做标题或关联，这里生成新 UUID
        conversation_id = str(uuid.uuid4())
        
        new_conversation = Conversation(
            id=conversation_id,
            project_id=project_id,
            user_id=user_id,
            owner_id=owner_id,
            title=f"{request.question[:30]}..." if request.question else "New Chat",
            status="active",
            message_count=0,
            sensitivity="internal",      # 必填
            tags=[],                     # 必填
            is_encrypted=False,          # 必填
            is_deleted=False,            # 必填
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db.add(new_conversation)
        # 先 flush 一下，确保会话存在 (虽然 UUID 是生成的，但为了 ORM 状态同步)
        db.flush() 

        # 3. 调用 PromptFlow (保留您原有的核心逻辑)
        async with httpx.AsyncClient(timeout=60.0) as client:
            pf_payload = {
                "inputs": {
                    "question": request.question,
                    "chat_history": request.history
                }
            }
            if request.override_config:
                pf_payload["inputs"].update(request.override_config)

            resp = await client.post(PROMPTFLOW_ENDPOINT, json=pf_payload)
            
            if resp.status_code != 200:
                raise HTTPException(status_code=resp.status_code, detail=f"PromptFlow Error: {resp.text[:200]}")
            
            result = resp.json()
            answer = ""
            if isinstance(result, dict):
                answer = result.get('output', result.get('result', result.get('answer', str(result))))
            else:
                answer = str(result)

        # 4. 【新增】保存用户提问 (Message - User)
        user_msg = Message(
            id=str(uuid.uuid4()),
            conversation_id=conversation_id,
            role="user",
            content=request.question,
            status="completed",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            is_deleted=False
        )
        db.add(user_msg)

        # 5. 【新增】保存 AI 回答 (Message - Assistant)
        ai_msg = Message(
            id=str(uuid.uuid4()),
            conversation_id=conversation_id,
            role="assistant",
            content=answer,
            status="completed",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            is_deleted=False
        )
        db.add(ai_msg)

        # 6. 【新增】更新会话计数
        new_conversation.message_count = 2
        new_conversation.updated_at = datetime.utcnow()

        # 7. 【新增】统一提交事务
        db.commit()
        print(f"[Flowise Bridge] ✅ 对话已保存至 DB: ConvID={conversation_id}")

        # 8. 返回结果
        return FlowiseResponse(
            text=answer, 
            question=request.question, 
            history=request.history,
            sessionId=conversation_id # 将会话 ID 返回给前端，方便后续追踪
        )

    except Exception as e:
        db.rollback() # 【重要】出错回滚，保证数据一致性
        print(f"[Flowise Bridge] ❌ 错误: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal Error: {str(e)}")