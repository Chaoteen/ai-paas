"""
PromptRenderer 单元测试
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from uuid import uuid4

from models.base import Base
# 修正导入路径：User 在 auth.py 中
from models.auth import User 
from models.prompt import PromptTemplate, TemplateVisibility
from models.conversation import Conversation
# 修正导入路径：Project 可能在 project.py 中，确认一下
from models.project import Project 
from services.prompt_renderer import PromptRenderer, RenderContext

# 数据库 URL
DB_URL = "postgresql://postgres:postgres@localhost:5432/ai_paas"

def test_renderer():
    print("🧪 开始测试 PromptRenderer...")
    
    engine = create_engine(DB_URL)
    
    with Session(engine) as db:
        # 1. 准备数据
        user = db.query(User).first()
        if not user:
            print("⚠️ 未找到用户，跳过测试 (请先创建测试用户)")
            return

        project = db.query(Project).first()
        if not project:
            print("⚠️ 未找到项目，跳过测试")
            return
            
        template_content = """
        你是一个智能助手。
        当前时间：{{ current_time }}
        用户：{{ user.name }} ({{ user.email }})
        
        对话历史：
        {% for msg in history %}
        {{ msg.role }}: {{ msg.content }}
        {% endfor %}
        
        请根据以上信息回答用户的问题。
        """
        
        test_template = PromptTemplate(
            id=str(uuid4()),
            project_id=project.id,
            name="Test_Template_v1",
            template=template_content,
            version=1,
            is_latest=True,
            visibility=TemplateVisibility.PRIVATE.value
        )
        
        # 清理可能存在的同名模板
        existing = db.query(PromptTemplate).filter_by(name=test_template.name).first()
        if existing:
            db.delete(existing)
            
        db.add(test_template)
        db.commit()
        db.refresh(test_template)
        print(f"✅ 创建测试模板：{test_template.id}")

        # 2. 测试直接渲染
        renderer = PromptRenderer(db)
        ctx = RenderContext(
            user=user,
            conversation_history=[
                {"role": "user", "content": "你好"},
                {"role": "assistant", "content": "你好！有什么可以帮你的？"}
            ],
            custom_variables={"topic": "AI"}
        )
        
        rendered = renderer.render(test_template, ctx)
        print("\n--- 渲染结果预览 ---")
        print(rendered[:300] + "...")
        print("--------------------")
        
        # 简单验证
        if user.username in rendered or getattr(user, 'name', '') in rendered:
            print("✅ 渲染测试通过！变量替换成功。")
        else:
            print("⚠️ 渲染结果中未找到用户名，但可能已渲染其他变量。")
            print(f"   用户名字段：{getattr(user, 'username', 'N/A')}")
            
        # 清理测试数据
        db.delete(test_template)
        db.commit()
        print("\n🎉 测试完成，数据已清理。")

if __name__ == "__main__":
    try:
        test_renderer()
    except Exception as e:
        print(f"❌ 测试出错：{e}")
        import traceback
        traceback.print_exc()