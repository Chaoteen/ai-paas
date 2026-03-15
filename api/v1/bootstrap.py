from fastapi import APIRouter, Depends, HTTPException
from typing import List, Dict, Any, Optional

# 假设您有一个获取当前用户的依赖项，如果没有，我们先模拟一个
# from middleware.jwt_auth import get_current_user 
# def get_current_user(token: str = Depends(...)): ...

router = APIRouter(prefix="/ui", tags=["UI Bootstrap"])

@router.get("/bootstrap")
async def get_bootstrap_data():
    """
    提供前端初始化所需的全局配置：
    1. 当前用户信息
    2. 动态菜单配置
    3. 功能特性开关
    """
    
    # --- 1. 模拟当前用户信息 (实际应从 Token 解析) ---
    # 如果您有真实的 JWT 解析逻辑，请替换此处
    current_user = {
        "id": "user-001",
        "display_name": "Admin User",
        "is_admin": True,
        "email": "admin@ai-paas.com"
    }

    # --- 2. 定义动态菜单结构 ---
    # 这对应前端的 MenuItem[] 类型
    menus = [
        {
            "id": "menu-prompt",
            "title": "Prompt 工程",
            "icon": "Terminal",  # 前端需映射图标
            "route": "/prompts",
            "type": "page",
            "capability": "prompt.manage"
        },
        {
            "id": "menu-agent",
            "title": "Agent 管理",
            "icon": "Cpu",
            "route": "/agents",
            "type": "page",
            "capability": "agent.manage"
        },
        {
            "id": "menu-knowledge",
            "title": "知识库 (RAG)",
            "icon": "Database",
            "route": "/knowledge",
            "type": "page",
            "capability": "knowledge.manage"
        },
        {
            "id": "menu-settings",
            "title": "系统设置",
            "icon": "Settings",
            "route": "/settings",
            "type": "page",
            "capability": "system.settings"
        }
    ]

    # --- 3. 功能特性开关 ---
    features = {
        "enable_rag": True,
        "enable_agent_market": False,
        "enable_audit_log": True
    }

    # --- 4. 构建返回数据 ---
    bootstrap_data = {
        "user": current_user,
        "tenant": {
            "id": "tenant-default",
            "name": "AI-PaaS Default Tenant"
        },
        "menus": menus,
        "features": features,
        "capabilities": {
            "prompt.manage": True,
            "agent.manage": True,
            "knowledge.manage": True
        },
        "layout": {
            "sidebar_collapsible": True,
            "theme": "light"
        }
    }

    return bootstrap_data