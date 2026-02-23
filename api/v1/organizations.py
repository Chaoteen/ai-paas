"""
组织管理 API 模块
提供组织的 CRUD 操作
"""
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from models.auth import Organization, OrganizationMember, User
from models.database import get_db
from middleware.jwt_auth import require_auth
from config.settings import settings


router = APIRouter(prefix="/organizations", tags=["组织管理"])


# ==================== Pydantic 模型 ====================
from pydantic import BaseModel, Field
from datetime import datetime


class OrganizationCreateRequest(BaseModel):
    """创建组织请求"""
    name: str = Field(..., min_length=1, max_length=100)


class OrganizationUpdateRequest(BaseModel):
    """更新组织请求"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    is_active: Optional[bool] = None


class OrganizationMemberRequest(BaseModel):
    """添加组织成员请求"""
    user_email: str
    role: str = Field(..., pattern="^(owner|admin|member|viewer)$")


class OrganizationResponse(BaseModel):
    """组织响应"""
    id: str
    name: str
    owner_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    is_active: bool = True
    member_count: int = 0


class OrganizationMemberResponse(BaseModel):
    """组织成员响应"""
    user_id: str
    email: str
    full_name: Optional[str]
    role: str
    joined_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class OrganizationListResponse(BaseModel):
    """组织列表响应"""
    items: List[OrganizationResponse]
    total: int
    page: int
    page_size: int


# ==================== 辅助函数 ====================
def get_organization_or_404(
    org_id: str,
    db: Session
) -> Organization:
    """获取组织或抛出 404"""
    try:
        uuid_org_id = UUID(org_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid organization ID format"
        )
    
    org = db.query(Organization).filter(Organization.id == uuid_org_id).first()
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found"
        )
    return org


def check_organization_permission(
    org: Organization,
    user: User,
    db: Session,
    required_role: str = "member"
) -> OrganizationMember:
    """
    检查用户对组织的权限
    
    Args:
        org: 组织对象
        user: 用户对象
        db: 数据库会话
        required_role: 所需最低角色 (owner > admin > member > viewer)
    """
    role_hierarchy = {"owner": 4, "admin": 3, "member": 2, "viewer": 1}
    
    member = db.query(OrganizationMember).filter(
        OrganizationMember.organization_id == org.id,
        OrganizationMember.user_id == user.id
    ).first()
    
    if not member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a member of this organization"
        )
    
    if role_hierarchy.get(member.role, 0) < role_hierarchy.get(required_role, 0):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Insufficient permissions. Required: {required_role}"
        )
    
    return member


# ==================== API 端点 ====================

@router.get("", response_model=OrganizationListResponse)
async def list_organizations(
    current_user: User = Depends(require_auth),
    db: Session = Depends(get_db),
    page: int = 1,
    page_size: int = settings.DEFAULT_PAGE_SIZE
):
    """
    获取当前用户所属的组织列表
    """
    # 限制页大小
    page_size = min(page_size, settings.MAX_PAGE_SIZE)
    offset = (page - 1) * page_size
    
    # 查询用户所属组织
    from sqlalchemy import func
    query = db.query(Organization).join(
        OrganizationMember,
        Organization.id == OrganizationMember.organization_id
    ).filter(
        OrganizationMember.user_id == current_user.id,
    )    
    
    total = query.count()
    orgs = query.offset(offset).limit(page_size).all()
    
    # 获取每个组织的成员数量
    items = []
    for org in orgs:
        member_count = db.query(OrganizationMember).filter(
            OrganizationMember.organization_id == org.id
        ).count()
        
        items.append(OrganizationResponse(
            id=str(org.id),
            name=org.name,
            owner_id=str(org.owner_id) if org.owner_id else None,
            created_at=org.created_at,
            updated_at=org.updated_at,
            member_count=member_count
        ))
    
    return OrganizationListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size
    )


@router.post("", response_model=OrganizationResponse)
async def create_organization(
    request: OrganizationCreateRequest,
    current_user: User = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """
    创建新组织
    
    创建者自动成为组织 owner
    """
    # 检查组织名是否已存在
    existing = db.query(Organization).filter(
        Organization.name == request.name,
        Organization.owner_id == current_user.id
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Organization name already exists"
        )
    
    # 创建组织
    # 在 api/v1/organizations.py 中，找到 Organization 创建部分，修改为：
    org = Organization(
        name=request.name,
        slug=request.name.lower().replace(' ', '-'),  # 添加 slug
        owner_id=current_user.id,
        plan="free",                                   # 添加 plan
        sensitivity_default="internal",                # 添加 sensitivity_default
        compliance_tags=[],                            # 添加 compliance_tags
        allowed_locations=["US"],                      # 添加 allowed_locations
        data_residency="US"                            # 添加 data_residency
    )
    
    db.add(org)
    db.flush()
    
    # 添加创建者为 owner
    member = OrganizationMember(
        organization_id=org.id,
        user_id=current_user.id,
        role="owner"
    )
    db.add(member)
    
    db.commit()
    db.refresh(org)
    
    return OrganizationResponse(
        id=str(org.id),
        name=org.name,
        owner_id=str(org.owner_id),
        created_at=org.created_at,
        updated_at=org.updated_at,
        member_count=1
    )


@router.get("/{org_id}", response_model=OrganizationResponse)
async def get_organization(
    org_id: str,
    current_user: User = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """
    获取组织详情
    """
    org = get_organization_or_404(org_id, db)
    
    # 检查权限
    check_organization_permission(org, current_user, db, "viewer")
    
    # 获取成员数量
    member_count = db.query(OrganizationMember).filter(
        OrganizationMember.organization_id == org.id
    ).count()
    
    return OrganizationResponse(
        id=str(org.id),
        name=org.name,
        owner_id=str(org.owner_id),
        created_at=org.created_at,
        updated_at=org.updated_at,
        member_count=member_count
    )


@router.put("/{org_id}", response_model=OrganizationResponse)
async def update_organization(
    org_id: str,
    request: OrganizationUpdateRequest,
    current_user: User = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """
    更新组织信息
    
    需要 admin 或 owner 权限
    """
    org = get_organization_or_404(org_id, db)
    
    # 检查权限 (需要 admin 或 owner)
    check_organization_permission(org, current_user, db, "admin")
    
    # 更新字段
    if request.name is not None:
        org.name = request.name
    if request.is_active is not None:
        org.is_active = request.is_active
    
    db.commit()
    db.refresh(org)
    
    member_count = db.query(OrganizationMember).filter(
        OrganizationMember.organization_id == org.id
    ).count()
    
    return OrganizationResponse(
        id=str(org.id),
        name=org.name,
        owner_id=str(org.owner_id),
        created_at=org.created_at,
        updated_at=org.updated_at,
        member_count=member_count
    )


@router.delete("/{org_id}")
async def delete_organization(
    org_id: str,
    current_user: User = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """
    删除组织
    
    只有 owner 可以删除组织
    """
    org = get_organization_or_404(org_id, db)
    
    # 检查权限 (只有 owner 可以删除)
    check_organization_permission(org, current_user, db, "owner")
    
    # 软删除
    org.is_active = False
    
    db.commit()
    
    return {"message": "Organization deleted successfully"}


@router.get("/{org_id}/members", response_model=List[OrganizationMemberResponse])
async def list_organization_members(
    org_id: str,
    current_user: User = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """
    获取组织成员列表
    """
    org = get_organization_or_404(org_id, db)
    
    # 检查权限
    check_organization_permission(org, current_user, db, "member")
    
    # 查询成员
    members = db.query(OrganizationMember).filter(
        OrganizationMember.organization_id == org.id
    ).all()
    
    result = []
    for member in members:
        user = db.query(User).filter(User.id == member.user_id).first()
        if user:
            result.append(OrganizationMemberResponse(
                user_id=str(user.id),
                email=user.email,
                full_name=user.full_name,
                role=member.role,
                joined_at=member.joined_at
            ))
    
    return result


@router.post("/{org_id}/members")
async def add_organization_member(
    org_id: str,
    request: OrganizationMemberRequest,
    current_user: User = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """
    添加组织成员
    
    需要 admin 或 owner 权限
    """
    org = get_organization_or_404(org_id, db)
    
    # 检查权限
    check_organization_permission(org, current_user, db, "admin")
    
    # 查找用户
    user = db.query(User).filter(User.email == request.user_email).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # 检查是否已是成员
    existing = db.query(OrganizationMember).filter(
        OrganizationMember.organization_id == org.id,
        OrganizationMember.user_id == user.id
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is already a member of this organization"
        )
    
    # 添加成员
    member = OrganizationMember(
        organization_id=org.id,
        user_id=user.id,
        role=request.role
    )
    db.add(member)
    db.commit()
    
    return {"message": "Member added successfully"}


@router.delete("/{org_id}/members/{user_id}")
async def remove_organization_member(
    org_id: str,
    user_id: str,
    current_user: User = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """
    移除组织成员
    
    需要 admin 或 owner 权限
    """
    org = get_organization_or_404(org_id, db)
    
    # 检查权限
    check_organization_permission(org, current_user, db, "admin")
    
    # 不能移除 owner
    existing = db.query(OrganizationMember).filter(
        OrganizationMember.organization_id == org.id,
        OrganizationMember.user_id == user_id,
        OrganizationMember.role == "owner"
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot remove organization owner"
        )
    
    # 删除成员关系
    db.query(OrganizationMember).filter(
        OrganizationMember.organization_id == org.id,
        OrganizationMember.user_id == user_id
    ).delete()
    
    db.commit()
    
    return {"message": "Member removed successfully"}