"""
认证 API 模块
提供用户注册、登录、令牌刷新等功能
"""
from typing import Optional
from datetime import timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from models.auth import User, Organization, OrganizationMember
from models.database import get_db
from services.auth_service import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    verify_token,
    decode_token
)
from middleware.jwt_auth import require_auth, oauth2_scheme
from config.settings import settings
from pydantic import BaseModel, EmailStr, Field


router = APIRouter(prefix="/auth", tags=["认证"])


# ==================== Pydantic 模型 ====================

class UserRegisterRequest(BaseModel):
    """用户注册请求"""
    email: EmailStr
    password: str = Field(..., min_length=8, description="密码至少 8 位")
    full_name: Optional[str] = None
    organization_name: Optional[str] = None


class UserRegisterResponse(BaseModel):
    """用户注册响应"""
    user_id: str
    email: str
    organization_id: Optional[str] = None
    message: str


class UserLoginRequest(BaseModel):
    """用户登录请求"""
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """令牌响应"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class TokenRefreshRequest(BaseModel):
    """令牌刷新请求"""
    refresh_token: str


class UserInfoResponse(BaseModel):
    """用户信息响应"""
    user_id: str
    email: str
    full_name: Optional[str] = None
    role: str
    organization_id: Optional[str] = None
    is_admin: bool


# ==================== API 端点 ====================

@router.post("/register", response_model=UserRegisterResponse)
async def register(
    request: UserRegisterRequest,
    db: Session = Depends(get_db)
):
    """用户注册"""
    existing_user = db.query(User).filter(User.email == request.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    user = User(
        email=request.email,
        password_hash=hash_password(request.password),
        username=request.email.split('@')[0],
        status="active",
        role="developer",
        department="",
        level="L1",
        auth_level="basic",
        abac_attributes={}
    )
    
    db.add(user)
    db.flush()
    
    organization_id = None
    
    if request.organization_name:
        org = Organization(
            name=request.organization_name,
            slug=request.organization_name.lower().replace(" ", "-"),
            owner_id=user.id
        )
        db.add(org)
        db.flush()
        organization_id = str(org.id)
        
        member = OrganizationMember(
            organization_id=org.id,
            user_id=user.id,
            role="owner"
        )
        db.add(member)
    else:
        default_org_name = f"{request.email.split('@')[0]}'s Organization"
        org = Organization(
            name=default_org_name,
            slug=default_org_name.lower().replace(" ", "-"),
            owner_id=user.id
        )
        db.add(org)
        db.flush()
        organization_id = str(org.id)
        
        member = OrganizationMember(
            organization_id=org.id,
            user_id=user.id,
            role="owner"
        )
        db.add(member)
    
    db.commit()
    db.refresh(user)
    
    return UserRegisterResponse(
        user_id=str(user.id),
        email=user.email,
        organization_id=organization_id,
        message="User registered successfully"
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """用户登录 (OAuth2 密码流)"""
    user = db.query(User).filter(User.email == form_data.username).first()
    
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled"
        )
    
    org_member = db.query(OrganizationMember).filter(
        OrganizationMember.user_id == user.id
    ).first()
    organization_id = str(org_member.organization_id) if org_member else None
    
    access_token = create_access_token(
        subject=user.email,
        user_id=user.id,
        role=user.role,
        organization_id=organization_id
    )
    
    refresh_token = create_refresh_token(
        subject=user.email,
        user_id=user.id
    )
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


@router.post("/login/json", response_model=TokenResponse)
async def login_json(
    request: UserLoginRequest,
    db: Session = Depends(get_db)
):
    """用户登录 (JSON 格式)"""
    user = db.query(User).filter(User.email == request.email).first()
    
    if not user or not verify_password(request.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled"
        )
    
    org_member = db.query(OrganizationMember).filter(
        OrganizationMember.user_id == user.id
    ).first()
    organization_id = str(org_member.organization_id) if org_member else None
    
    access_token = create_access_token(
        subject=user.email,
        user_id=user.id,
        role=user.role,
        organization_id=organization_id
    )
    
    refresh_token = create_refresh_token(
        subject=user.email,
        user_id=user.id
    )
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token_endpoint(
    request: TokenRefreshRequest,
    db: Session = Depends(get_db)
):
    """刷新访问令牌"""
    payload = verify_token(request.refresh_token, token_type="refresh")
    
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
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
    
    if user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled"
        )
    
    org_member = db.query(OrganizationMember).filter(
        OrganizationMember.user_id == user.id
    ).first()
    organization_id = str(org_member.organization_id) if org_member else None
    
    access_token = create_access_token(
        subject=user.email,
        user_id=user.id,
        role=user.role,
        organization_id=organization_id
    )
    
    new_refresh_token = create_refresh_token(
        subject=user.email,
        user_id=user.id
    )
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


@router.get("/me", response_model=UserInfoResponse)
async def get_current_user_info(
    current_user = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """获取当前用户信息"""
    org_member = db.query(OrganizationMember).filter(
        OrganizationMember.user_id == current_user.id
    ).first()
    organization_id = str(org_member.organization_id) if org_member else None
    
    return UserInfoResponse(
        user_id=str(current_user.id),
        email=current_user.email,
        full_name=getattr(current_user, 'username', current_user.email.split('@')[0]),
        role=current_user.role,
        organization_id=organization_id,
        is_admin=current_user.role in ["admin", "superadmin"]
    )


@router.post("/logout")
async def logout(
    current_user = Depends(require_auth)
):
    """用户登出"""
    return {"message": "Logged out successfully"}
