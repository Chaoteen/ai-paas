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
    生成 SSE 流式响应
    模拟 LLM 流式输出 (实际项目中这里会调用 LLM SDK 的 stream 接口)
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
            yield {"event": "error", "data": f"Prompt 渲染失败：{str(e)}"}
            return

        # 3. 模拟 LLM 流式生成 (TODO: 替换为真实的 LLM 调用)
        assistant_msg_id = str(uuid4())
        assistant_content = ""
        
        yield {"event": "start", "data": {"message_id": assistant_msg_id}}

        # 模拟流式输出文本
        response_text = f"[模拟回复] 收到你的消息：'{user_message_content}'。\n\n已渲染 Prompt 长度：{len(full_prompt)} 字符。\n(此处应接入真实 LLM)"
        
        for char in response_text:
            assistant_content += char
            yield {"event": "token", "data": char}
            await asyncio.sleep(0.05) 

        # 4. 保存助手消息
        assistant_msg = Message(
            id=assistant_msg_id,
            conversation_id=conversation_id,
            role="assistant",
            content=assistant_content,
            status="completed",
            metadata={"prompt_length": len(full_prompt)}
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
        
        yield {"event": "end", "data": {"message_id": assistant_msg_id, "content": assistant_content}}

    except Exception as e:
        yield {"event": "error", "data": f"服务器内部错误：{str(e)}"}
        if db:
            db.rollback()

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
        if str(template.project_id) != str(payload.project_id):  # 修复 UUID vs str 比较问题
            raise HTTPException(status_code=400, detail="Template does not belong to this project")

    new_conv = Conversation(
        id=str(uuid4()),
        project_id=payload.project_id,
        agent_id=payload.agent_id,
        user_id=None, # 当前硬编码为 None，未来从 Auth 获取
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
    不使用数据库中的模板，直接渲染传入的字符串
    """
    # 创建一个临时模板对象 (不保存)
    temp_template = PromptTemplate(
        id="temp",
        project_id="temp",
        name="Temp",
        template=template_content,
        version=1
    )
    
    # 构造一个 Mock 上下文
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