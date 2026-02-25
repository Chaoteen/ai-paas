"""
AI-PaaS 平台主应用入口
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from config.settings import settings
from models.database import engine, Base
from api.v1 import api_v1_router
from middleware.jwt_auth import JWTAuthMiddleware
from api.v1 import agents
# [新增] 导入 conversations 路由模块
from api.v1 import conversations


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时
    print(f"🚀 Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    print(f"📊 Debug mode: {settings.DEBUG}")
    
    # 创建数据库表
    # 注意：在生产环境中通常使用 Alembic 迁移，这里仅用于开发快速启动
    Base.metadata.create_all(bind=engine)
    print("✅ Database tables created")
    
    yield
    
    # 关闭时
    print("👋 Shutting down...")


# 创建 FastAPI 应用
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="AI 开发者 PaaS 平台 - 提供 Agent 编排、工作流管理、权限控制等功能",
    lifespan=lifespan
)

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 添加 JWT 认证中间件
# app.add_middleware(JWTAuthMiddleware)

# 包含 API 路由
# 通用 V1 路由 (如果 api_v1_router 包含了子路由聚合，保留此行)
app.include_router(api_v1_router)

# Agents 模块路由
app.include_router(agents.router, prefix="/api/v1/agents", tags=["agents"])

# [新增] Conversations 模块路由
# 注意：conversations.py 内部已经定义了 prefix="/conversations"，所以这里只需加 /api/v1
app.include_router(conversations.router, prefix="/api/v1/conversations", tags=["conversations"])


# 健康检查端点
@app.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "version": settings.APP_VERSION
    }


# 根路径
@app.get("/")
async def root():
    """根路径"""
    return {
        "message": f"Welcome to {settings.APP_NAME}",
        "docs": "/docs",
        "health": "/health"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG
    )