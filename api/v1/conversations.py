"""
Conversation API Routes
支持创建会话、发送消息 (SSE 流式)、历史记录查询、Prompt 预览
"""
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Body
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from datetime import datetime
from uuid import uuid4, UUID
import asyncio
import json  # 确保导入 json
# 本地导入
from models.database import get_db
from models.conversation import Conversation, Message, MessageRole
from models.prompt import PromptTemplate
from models.project import Project
from services.prompt_renderer import PromptRenderer, RenderContext

router = APIRouter(tags=["Conversations"])

# ================= Pydantic Schemas =================

class MessageCreate(BaseModel):
    content: str = Field(..., min_length=1, description="消息内容")
    role: str = Field(default="user", description="角色 (user/assistant)")

class ConversationCreate(BaseModel):
    project_id: str = Field(..., description="项目 ID")
    agent_id: Optional[str] = Field(None, description="关联 Agent ID")
    title: Optional[str] = Field(default="New Conversation", description="会话标题")
    template_id: Optional[str] = Field(None, description="指定 Prompt 模板 ID")

class MessageResponse(BaseModel):
    id: UUID
    role: str
    content: str
    created_at: datetime
    
    class Config:
        from_attributes = True

class ConversationResponse(BaseModel):
    id: UUID
    title: Optional[str]
    status: str
    created_at: datetime
    
    class Config:
        from_attributes = True

# ================= Helper Functions =================

async def generate_stream_response(
    conversation_id: str,
    user_message_content: str,
    db: Session
):
    """
    生成 SSE 流式响应 (接入真实 LLM)
    [修复] 显式使用 json.dumps 序列化 data 字段，确保输出标准 JSON (双引号)
    """
    try:
        # 1. 保存用户消息
        user_msg = Message(
            id=str(uuid4()),
            conversation_id=conversation_id,
            role="user",
            content=user_message_content,
            status="completed"
        )
        db.add(user_msg)
        db.commit()

        # 2. 渲染 Prompt (使用之前测试通过的引擎)
        renderer = PromptRenderer(db)
        try:
            full_prompt = renderer.render_for_conversation(conversation_id)
        except ValueError as e:
            # 错误信息也序列化为 JSON 字符串
            yield {"event": "error", "data": json.dumps({"error": f"Prompt 渲染失败：{str(e)}"})}
            return

        # 3. 调用真实 LLM (流式)
        from services.llm_service import llm_service
        
        assistant_msg_id = str(uuid4())
        assistant_content = ""
        
        # [修复] data 字段强制转为 JSON 字符串
        yield {"event": "start", "data": json.dumps({"message_id": assistant_msg_id})}

        # 构建发送给 LLM 的消息列表
        llm_messages = [
            {"role": "system", "content": full_prompt},
            {"role": "user", "content": user_message_content}
        ]
        
        print(f"🚀 正在调用 {llm_service.provider} 模型 ({llm_service.model_name})...")
        
        # 流式获取回复
        async for token in llm_service.chat_stream(llm_messages):
            assistant_content += token
            # [修复] token 是字符串，json.dumps 会给它加上双引号，变成合法的 JSON 字符串
            yield {"event": "token", "data": json.dumps(token)}

        # 4. 保存助手消息
        assistant_msg = Message(
            id=assistant_msg_id,
            conversation_id=conversation_id,
            role="assistant",
            content=assistant_content,
            status="completed",
            metadata={
                "prompt_length": len(full_prompt),
                "provider": llm_service.provider,
                "model": llm_service.model_name
            }
        )
        db.add(assistant_msg)
        
        # 更新会话消息计数
        conv = db.query(Conversation).get(conversation_id)
        if conv:
            conv.message_count += 1
            # 如果是第一条消息，自动生成标题
            if conv.message_count == 1 and not conv.title:
                conv.title = user_message_content[:30] + "..."
        
        db.commit()
        
        # [修复] data 字段强制转为 JSON 字符串
        yield {"event": "end", "data": json.dumps({"message_id": assistant_msg_id, "content": assistant_content})}

    except Exception as e:
        yield {"event": "error", "data": json.dumps({"error": f"服务器内部错误：{str(e)}"})}
        if db:
            db.rollback()
        import traceback
        traceback.print_exc()

# ================= API Endpoints =================

@router.post("/", response_model=ConversationResponse)
def create_conversation(
    payload: ConversationCreate,
    db: Session = Depends(get_db)
):
    """创建新会话"""
    # 验证 Project 存在
    project = db.query(Project).filter(Project.id == payload.project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # 如果指定了 template_id，验证其存在
    if payload.template_id:
        template = db.query(PromptTemplate).filter(PromptTemplate.id == payload.template_id).first()
        if not template:
            raise HTTPException(status_code=404, detail="Prompt Template not found")
        # 确保模板属于该项目
        if str(template.project_id) != str(payload.project_id):
            raise HTTPException(status_code=400, detail="Template does not belong to this project")

    new_conv = Conversation(
        id=str(uuid4()),
        project_id=payload.project_id,
        agent_id=payload.agent_id,
        user_id=None,
        title=payload.title,
        status="active",
        prompt_template_id=payload.template_id
    )
    
    db.add(new_conv)
    db.commit()
    db.refresh(new_conv)
    
    return new_conv

@router.get("/{conv_id}/messages")
def get_messages(
    conv_id: str,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """获取会话历史消息"""
    conv = db.query(Conversation).filter(Conversation.id == conv_id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    messages = (
        db.query(Message)
        .filter(Message.conversation_id == conv_id)
        .order_by(Message.created_at.asc())
        .limit(limit)
        .all()
    )
    
    return messages

@router.post("/{conv_id}/messages")
def send_message_stream(
    conv_id: str,
    payload: MessageCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    发送消息并接收 SSE 流式响应
    Content-Type: text/event-stream
    """
    conv = db.query(Conversation).filter(Conversation.id == conv_id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    if conv.status != "active":
        raise HTTPException(status_code=400, detail="Conversation is not active")

    # 返回 EventSourceResponse (SSE)
    return EventSourceResponse(
        generate_stream_response(conv_id, payload.content, db),
        media_type="text/event-stream"
    )

@router.post("/templates/preview")
def preview_prompt(
    template_content: str = Body(..., description="Jinja2 模板内容", embed=True),
    custom_vars: Optional[Dict[str, Any]] = Body(None, description="自定义变量 JSON", embed=True),
    db: Session = Depends(get_db)
):
    """
    在线调试 Prompt 模板
    """
    temp_template = PromptTemplate(
        id="temp",
        project_id="temp",
        name="Temp",
        template=template_content,
        version=1
    )
    
    class MockUser:
        id = "mock-id"
        username = "TestUser"
        email = "test@example.com"
    
    ctx = RenderContext(
        user=MockUser(),
        conversation_history=[{"role": "user", "content": "Hello"}],
        custom_variables=custom_vars or {}
    )
    
    renderer = PromptRenderer(db)
    try:
        rendered = renderer.render(temp_template, ctx)
        return {"success": True, "rendered_content": rendered}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))