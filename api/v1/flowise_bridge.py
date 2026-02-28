from fastapi import APIRouter, HTTPException, Header, Depends, status
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import httpx
import os
import uuid
import traceback
from datetime import datetime, timezone

# 【数据库相关导入】
from sqlalchemy.orm import Session
from models.database import get_db
from models.conversation import Conversation, Message
from models.project import Project

router = APIRouter(prefix="/flowise", tags=["Flowise Integration"])

# 配置项
PF_BASE_URL = os.getenv("PROMPTFLOW_SERVICE_URL", "http://127.0.0.1:8080/score")
PROMPTFLOW_ENDPOINT = PF_BASE_URL

# 【鉴权逻辑】
# 暂时简化验证，确保 Flowise 能通。生产环境请恢复严格的 JWT 或 API Key 校验。
async def verify_api_key(x_api_key: Optional[str] = Header(None)):
    # 这里可以添加具体的 key 比对逻辑，目前直接返回一个调试标识
    return "debug-key-verified"

class FlowiseRequest(BaseModel):
    question: str
    chatId: Optional[str] = None
    history: Optional[List[Dict[str, str]]] = []
    override_config: Optional[Dict[str, Any]] = {}

class FlowiseResponse(BaseModel):
    text: str
    question: str
    history: Optional[List[Dict[str, str]]] = []
    sessionId: Optional[str] = None

# ... (文件顶部的 import 保持不变) ...

# 【修改点 1】移除 response_model=FlowiseResponse
# 这样 FastAPI 会根据实际返回类型（str）自动处理响应
@router.post("/execute")
async def execute_prompt(
    request: FlowiseRequest,
    api_key: str = Depends(verify_api_key),
    db: Session = Depends(get_db)
):
    """
    Flowise 专用接口：接收用户问题 -> 调用 PromptFlow -> 保存对话到 DB -> 返回结果
    """
    print(f"[Flowise Bridge] 收到请求：{request.question[:50]}...")
    
    # 默认用户 ID (TODO: 未来从 JWT Token 中解析真实用户 ID)
    DEFAULT_USER_ID = "f92cc300-90cc-467c-a28e-60f2b87254bb" 
    user_id = DEFAULT_USER_ID
    owner_id = user_id

    try:
        # 1. 获取或创建项目 (取第一个项目作为默认)
        project = db.query(Project).first()
        if not project:
            raise HTTPException(status_code=500, detail="No project found in database. Please create a project first.")
        project_id = project.id

        # 2. 创建会话 (Conversation)
        conversation_id = str(uuid.uuid4())
        
        # 【关键数据准备】
        sensitivity_val = "internal"
        tags_val = [] 
        
        # 动态检查 Conversation 模型是否有 owner_id 字段
        from sqlalchemy.inspection import inspect
        mapper = inspect(Conversation)
        has_owner_id = "owner_id" in [c.key for c in mapper.columns]

        conversation_kwargs = {
            "id": conversation_id,
            "project_id": project_id,
            "user_id": user_id,
            "title": f"{request.question[:30]}..." if request.question else "New Chat",
            "status": "active",
            "message_count": 0,
            "sensitivity": sensitivity_val,
            "tags": tags_val,
            "is_encrypted": False,
            "is_deleted": False,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }
        
        if has_owner_id:
            conversation_kwargs["owner_id"] = owner_id
        else:
            print("[Warning] Conversation 模型中未找到 owner_id 字段，已自动跳过。")

        new_conversation = Conversation(**conversation_kwargs)
        
        db.add(new_conversation)
        db.flush() 

        # 3. 调用 PromptFlow
        async with httpx.AsyncClient(timeout=60.0) as client:
            pf_payload = {
                "inputs": {
                    "question": request.question,
                    "chat_history": request.history
                }
            }
            if request.override_config:
                pf_payload["inputs"].update(request.override_config)

            print(f"[Flowise Bridge] 正在调用 PromptFlow: {PROMPTFLOW_ENDPOINT}")
            resp = await client.post(PROMPTFLOW_ENDPOINT, json=pf_payload)
            
            if resp.status_code != 200:
                raise HTTPException(status_code=resp.status_code, detail=f"PromptFlow Error: {resp.text[:200]}")
            
            result = resp.json()
            answer = ""
            if isinstance(result, dict):
                answer = result.get('output', result.get('result', result.get('answer', str(result))))
            else:
                answer = str(result)

        # 4. 保存用户提问 (Message - User)
        now = datetime.now(timezone.utc)
        
        user_msg = Message(
            id=str(uuid.uuid4()),
            conversation_id=conversation_id,
            role="user",
            content=request.question,
            status="completed",
            created_at=now,
            updated_at=now,
            is_deleted=False
        )
        db.add(user_msg)

        # 5. 保存 AI 回答 (Message - Assistant)
        ai_msg = Message(
            id=str(uuid.uuid4()),
            conversation_id=conversation_id,
            role="assistant",
            content=answer,
            status="completed",
            created_at=now,
            updated_at=now,
            is_deleted=False
        )
        db.add(ai_msg)

        # 6. 更新会话计数
        new_conversation.message_count = 2
        new_conversation.updated_at = now

        # 7. 统一提交事务
        db.commit()
        print(f"[Flowise Bridge] ✅ 对话已成功保存至 DB: ConvID={conversation_id}")

        # 【修改点 2】直接返回纯文本字符串 answer
        # 这样 Flowise 就能直接拿到文本，不再报 "Missing value for input variable 'text'"
        return answer

    except Exception as e:
        db.rollback()
        
        # 【关键调试】打印完整堆栈信息到终端
        error_stack = traceback.format_exc()
        print(f"[Flowise Bridge] ❌ 发生严重错误，详细堆栈如下:\n{error_stack}")
        
        # 提取关键错误信息返回给前端
        error_msg = str(e)
        if "IntegrityError" in str(type(e)) or "mismatched schema" in error_msg.lower():
            error_msg += " (提示：可能是数据库字段缺失、枚举值不匹配或 NOT NULL 约束冲突。请查看后端终端日志获取详细列名。)"
        
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {error_msg}")