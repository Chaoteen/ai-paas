"""
数据库连接配置
提供 SQLAlchemy 引擎和会话管理
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from typing import Generator

# 数据库 URL
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://postgres:postgres@localhost:5432/ai_paas"
)

# 创建引擎
engine = create_engine(
    DATABASE_URL,
    echo=False,  # 生产环境设为 False
    pool_pre_ping=True,  # 连接健康检查
    pool_size=10,
    max_overflow=20
)

# 创建会话工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 创建基类
Base = declarative_base()


def get_db() -> Generator:
    """
    获取数据库会话的依赖注入函数
    用于 FastAPI 路由的 Depends()
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """初始化数据库（创建所有表）"""
    Base.metadata.create_all(bind=engine)


def drop_db():
    """删除所有表（慎用！）"""
    Base.metadata.drop_all(bind=engine)