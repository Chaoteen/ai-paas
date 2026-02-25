"""
提示词渲染引擎 (Prompt Renderer)
基于 Jinja2 实现动态模板渲染，支持版本控制和上下文注入。
"""
import os
from typing import Dict, Any, Optional, List
from datetime import datetime
from jinja2 import Template, StrictUndefined, UndefinedError
from sqlalchemy.orm import Session, joinedload

from models.prompt import PromptTemplate
from models.conversation import Conversation, Message
# 修正导入：User 在 auth.py 中
from models.auth import User 

class RenderContext:
    """渲染上下文数据类"""
    def __init__(
        self,
        user: Optional[User] = None,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        current_time: Optional[datetime] = None,
        custom_variables: Optional[Dict[str, Any]] = None
    ):
        self.user = user
        self.history = conversation_history or []
        self.current_time = current_time or datetime.now()
        self.custom_vars = custom_variables or {}

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典供 Jinja2 使用"""
        data = {
            "current_time": self.current_time.strftime("%Y-%m-%d %H:%M:%S"),
            "history": self.history,
            "history_count": len(self.history),
        }
        
        if self.user:
            # 动态获取用户名，兼容 username 或 name 字段
            user_name = getattr(self.user, "username", getattr(self.user, "name", "Unknown"))
            user_email = getattr(self.user, "email", "")
            
            data["user"] = {
                "id": str(self.user.id),
                "name": user_name,
                "email": user_email,
            }
        
        # 合并自定义变量
        data.update(self.custom_vars)
        
        return data


class PromptRenderer:
    """提示词渲染器"""

    def __init__(self, db_session: Session):
        self.db = db_session
        # 配置 Jinja2 环境
        self.env = {
            "undefined": StrictUndefined
        }

    def get_active_template(self, project_id: str) -> Optional[PromptTemplate]:
        """
        获取指定项目下当前激活的最新模板
        (原逻辑是按 agent_id，现调整为按 project_id，因为模板属于项目)
        """
        template = (
            self.db.query(PromptTemplate)
            .filter(
                PromptTemplate.project_id == project_id,
                PromptTemplate.is_active == True
            )
            .order_by(PromptTemplate.version.desc())
            .first()
        )
        return template

    def get_template_by_id(self, template_id: str) -> Optional[PromptTemplate]:
        """
        通过 ID 获取特定版本的模板 (用于会话快照)
        """
        return (
            self.db.query(PromptTemplate)
            .filter(PromptTemplate.id == template_id)
            .options(joinedload(PromptTemplate.project))
            .first()
        )

    def render(self, template: PromptTemplate, context: RenderContext) -> str:
        """
        渲染模板
        :param template: PromptTemplate 对象
        :param context: RenderContext 对象
        :return: 渲染后的字符串
        """
        try:
            jinja_template = Template(template.template, undefined=StrictUndefined)
            variables = context.to_dict()
            
            return jinja_template.render(**variables)
            
        except UndefinedError as e:
            raise ValueError(f"模板渲染失败：缺少变量 - {e}")
        except Exception as e:
            raise ValueError(f"模板语法错误或渲染异常：{str(e)}")

    def render_for_conversation(
        self, 
        conversation_id: str, 
        custom_variables: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        便捷方法：为指定会话渲染 Prompt
        自动加载会话关联的模板、用户和历史记录
        """
        # 1. 加载会话 (带关系)
        conversation = (
            self.db.query(Conversation)
            .options(
                joinedload(Conversation.prompt_template),
                joinedload(Conversation.user),
                joinedload(Conversation.messages)
            )
            .filter(Conversation.id == conversation_id)
            .first()
        )
        
        if not conversation:
            raise ValueError(f"会话不存在：{conversation_id}")
            
        template = conversation.prompt_template
        
        # 如果没有绑定模板，且未来需要支持从 Agent 获取，可在此扩展
        if not template:
            raise ValueError("未找到可用的提示词模板 (会话未绑定模板)")

        # 2. 构建历史记录
        history_limit = 20
        messages = conversation.messages[-history_limit:]
        history_data = [
            {"role": msg.role, "content": msg.content}
            for msg in messages
            if msg.content
        ]

        # 3. 构建上下文
        ctx = RenderContext(
            user=conversation.user,
            conversation_history=history_data,
            custom_variables=custom_variables
        )

        # 4. 渲染
        return self.render(template, ctx)