"""
认证服务层
处理用户认证、令牌生成与验证等核心逻辑
"""
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from uuid import UUID

from passlib.context import CryptContext
from jose import jwt, JWTError

from config.settings import settings


# 密码加密上下文
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """
    对密码进行哈希加密
    
    Args:
        password: 明文密码
        
    Returns:
        哈希后的密码字符串
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    验证密码是否匹配
    
    Args:
        plain_password: 明文密码
        hashed_password: 哈希密码
        
    Returns:
        密码是否匹配
    """
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception:
        return False


def create_access_token(
    subject: str,
    user_id: UUID,
    role: str,
    organization_id: Optional[UUID] = None,
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    创建访问令牌 (JWT)
    
    Args:
        subject: 令牌主题 (通常是邮箱)
        user_id: 用户 ID
        role: 用户角色
        organization_id: 组织 ID (可选)
        expires_delta: 过期时间增量
        
    Returns:
        JWT 令牌字符串
    """
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + settings.get_access_token_expires()
    
    to_encode: Dict[str, Any] = {
        "sub": subject,
        "user_id": str(user_id),
        "role": role,
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "access"
    }
    
    if organization_id:
        to_encode["organization_id"] = str(organization_id)
    
    encoded_jwt = jwt.encode(
        to_encode, 
        settings.SECRET_KEY, 
        algorithm=settings.ALGORITHM
    )
    
    return encoded_jwt


def create_refresh_token(
    subject: str,
    user_id: UUID,
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    创建刷新令牌
    
    Args:
        subject: 令牌主题
        user_id: 用户 ID
        expires_delta: 过期时间增量
        
    Returns:
        JWT 刷新令牌字符串
    """
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + settings.get_refresh_token_expires()
    
    to_encode: Dict[str, Any] = {
        "sub": subject,
        "user_id": str(user_id),
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "refresh"
    }
    
    encoded_jwt = jwt.encode(
        to_encode, 
        settings.SECRET_KEY, 
        algorithm=settings.ALGORITHM
    )
    
    return encoded_jwt


def decode_token(token: str) -> Optional[Dict[str, Any]]:
    """
    解码 JWT 令牌
    
    Args:
        token: JWT 令牌字符串
        
    Returns:
        解码后的 payload 字典，如果无效则返回 None
    """
    try:
        payload = jwt.decode(
            token, 
            settings.SECRET_KEY, 
            algorithms=[settings.ALGORITHM]
        )
        return payload
    except JWTError:
        return None


def verify_token(token: str, token_type: str = "access") -> Optional[Dict[str, Any]]:
    """
    验证令牌是否有效
    
    Args:
        token: JWT 令牌字符串
        token_type: 令牌类型 (access/refresh)
        
    Returns:
        验证通过的 payload，否则返回 None
    """
    payload = decode_token(token)
    
    if payload is None:
        return None
    
    # 验证令牌类型
    if payload.get("type") != token_type:
        return None
    
    # 验证用户 ID 存在
    if payload.get("user_id") is None:
        return None
    
    return payload


def get_token_subject(token: str) -> Optional[str]:
    """
    从令牌中获取主题 (邮箱)
    
    Args:
        token: JWT 令牌字符串
        
    Returns:
        用户邮箱或 None
    """
    payload = decode_token(token)
    if payload:
        return payload.get("sub")
    return None