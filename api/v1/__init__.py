"""
API v1 模块
"""
from fastapi import APIRouter

# 导入所有 v1 路由
from api.v1.auth import router as auth_router
from api.v1.organizations import router as organizations_router
from api.v1.projects import router as projects_router

# 创建 v1 主路由
api_v1_router = APIRouter(prefix="/api/v1")

# 包含所有子路由
api_v1_router.include_router(auth_router)
api_v1_router.include_router(organizations_router)
api_v1_router.include_router(projects_router)

__all__ = ["api_v1_router"]