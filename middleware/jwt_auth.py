"""
JWT 认证中间件
处理请求中的 JWT 令牌验证和用户信息注入
"""
from typing import Optional, Callable
from fastapi import Request, HTTPException, status, Depends
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.orm import Session

from services.auth_service import verify_token, decode_token
from models.auth import User
from models.database import get_db
from config.settings import settings


# OAuth2 密码流配置
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/v1/auth/login",
    auto_error=False
)


async def get_current_user_token(request: Request) -> Optional[str]:
    """
    从请求头中获取 JWT 令牌
    
    Args:
        request: FastAPI 请求对象
        
    Returns:
        JWT 令牌字符串或 None
    """
    authorization = request.headers.get("Authorization")
    
    if not authorization:
        return None
    
    scheme, _, token = authorization.partition(" ")
    
    if scheme.lower() != "bearer":
        return None
    
    return token


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = None
) -> Optional[User]:
    """
    获取当前认证用户
    
    Args:
        token: JWT 令牌
        db: 数据库会话
        
    Returns:
        用户对象或 None
    """
    if not token:
        return None
    
    payload = verify_token(token, token_type="access")
    
    if payload is None:
        return None
    
    user_id = payload.get("user_id")
    
    if db and user_id:
        user = db.query(User).filter(User.id == user_id).first()
        return user
    
    return None


async def require_auth(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    """
    要求用户必须认证，否则抛出 401 异常
    """
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    payload = verify_token(token, token_type="access")
    
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user_id = payload.get("user_id")
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return user


async def get_current_user_from_request(request: Request) -> Optional[dict]:
    """
    从请求中解析当前用户信息 (用于中间件)
    
    Args:
        request: FastAPI 请求对象
        
    Returns:
        用户信息字典或 None
    """
    token = await get_current_user_token(request)
    
    if not token:
        return None
    
    payload = decode_token(token)
    
    if not payload:
        return None
    
    return {
        "user_id": payload.get("user_id"),
        "email": payload.get("sub"),
        "role": payload.get("role", "user"),
        "organization_id": payload.get("organization_id"),
        "is_admin": payload.get("role") == "admin"
    }


class JWTAuthMiddleware:
    """
    JWT 认证中间件类
    用于在请求处理前验证 JWT 令牌
    """
    
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        request = Request(scope)
        user_info = await get_current_user_from_request(request)
        
        # 将用户信息注入到请求状态中
        if user_info:
            request.state.user = user_info
            request.state.is_authenticated = True
        else:
            request.state.user = None
            request.state.is_authenticated = False
        
        await self.app(scope, receive, send)