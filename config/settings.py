"""
AI-PaaS 平台配置管理
配置所有环境变量和常量设置
"""
import os
import yaml
from typing import Optional
from datetime import timedelta
from pathlib import Path


# ==================== 路径配置 ====================
# 获取当前文件所在目录
BASE_DIR = Path(__file__).resolve().parent


# ==================== Settings 类 ====================
class Settings:
    """应用配置类"""
    
    # ==================== 应用基础配置 ====================
    APP_NAME: str = "AI-PaaS Platform"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"
    
    # ==================== 数据库配置 ====================
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", 
        "postgresql://postgres:postgres@localhost:5432/ai_paas"
    )
    
    # ==================== JWT 认证配置 ====================
    SECRET_KEY: str = os.getenv(
        "SECRET_KEY", 
        "your-super-secret-key-change-in-production-2026"
    )
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(
        os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60")
    )
    REFRESH_TOKEN_EXPIRE_DAYS: int = int(
        os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7")
    )
    # ==================== AI 模型配置 ====================
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "ollama")
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
    OLLAMA_MODEL_NAME: str = os.getenv("OLLAMA_MODEL_NAME", "deepseek-r1:latest")
    
    CLOUD_API_KEY: str = os.getenv("CLOUD_API_KEY", "")
    CLOUD_BASE_URL: str = os.getenv("CLOUD_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    CLOUD_MODEL_NAME: str = os.getenv("CLOUD_MODEL_NAME", "qwen-plus")

    
    # ==================== OPA 配置 ====================
    OPA_SERVER_URL: str = os.getenv(
        "OPA_SERVER_URL", 
        "http://localhost:8181"
    )
    OPA_POLICY_PATH: str = os.getenv(
        "OPA_POLICY_PATH", 
        "ui/allow"
    )
    
    # ==================== LangGraph 配置 ====================
    LANGGRAPH_SERVER_URL: str = os.getenv(
        "LANGGRAPH_SERVER_URL",
        "localhost:50051"
    )
    
    # ==================== 安全配置 ====================
    BCRYPT_ROUNDS: int = 12
    CORS_ORIGINS: list = [
        "http://localhost:3000",
        "http://localhost:8080",
        "http://127.0.0.1:3000",
    ]
    
    # ==================== 分页配置 ====================
    DEFAULT_PAGE_SIZE: int = 20
    MAX_PAGE_SIZE: int = 100
    
    # ==================== 配置方法 ====================
    def get_access_token_expires(self) -> timedelta:
        """获取访问令牌过期时间"""
        return timedelta(minutes=self.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    def get_refresh_token_expires(self) -> timedelta:
        """获取刷新令牌过期时间"""
        return timedelta(days=self.REFRESH_TOKEN_EXPIRE_DAYS)
    
    @property
    def pipelines(self) -> dict:
        """动态加载 pipelines.yaml 配置"""
        yaml_path = BASE_DIR / "pipelines.yaml"
        if not yaml_path.exists():
            return {}
        
        with open(yaml_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)


# ==================== 全局配置实例 ====================
settings = Settings()
