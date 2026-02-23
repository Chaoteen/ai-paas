"""
项目管理 API 模块
提供项目的 CRUD 操作
"""
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from models.project import Project, Environment, Integration
from models.auth import Organization, OrganizationMember, User
from models.database import get_db
from middleware.jwt_auth import require_auth
from config.settings import settings


router = APIRouter(prefix="/projects", tags=["项目管理"])


# ==================== Pydantic 模型 ====================
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum


class ProjectStatus(str, Enum):
    """项目状态"""
    ACTIVE = "active"
    ARCHIVED = "archived"
    SUSPENDED = "suspended"


class ProjectCreateRequest(BaseModel):
    """创建项目请求"""
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    organization_id: str
    slug: Optional[str] = None


class ProjectUpdateRequest(BaseModel):
    """更新项目请求"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    status: Optional[ProjectStatus] = None


class EnvironmentCreateRequest(BaseModel):
    """创建环境请求"""
    name: str = Field(..., min_length=1, max_length=50)
    description: Optional[str] = None
    config: Optional[dict] = None


class ProjectResponse(BaseModel):
    """项目响应"""
    id: str
    name: str
    slug: str
    description: Optional[str]
    organization_id: str
    owner_id: str
    status: str
    created_at: datetime
    updated_at: datetime
    environment_count: int = 0
    
    class Config:
        from_attributes = True


class EnvironmentResponse(BaseModel):
    """环境响应"""
    id: str
    name: str
    description: Optional[str]
    project_id: str
    config: Optional[dict]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class ProjectListResponse(BaseModel):
    """项目列表响应"""
    items: List[ProjectResponse]
    total: int
    page: int
    page_size: int


# ==================== 辅助函数 ====================
def get_project_or_404(
    project_id: str,
    db: Session
) -> Project:
    """获取项目或抛出 404"""
    try:
        uuid_project_id = UUID(project_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid project ID format"
        )
    
    project = db.query(Project).filter(Project.id == uuid_project_id).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    return project


def check_project_permission(
    org: Organization,
    user: User,
    db: Session
) -> OrganizationMember:
    """
    检查用户对项目的权限
    
    项目权限继承自组织权限
    """
    # 获取用户在该组织中的角色
    member = db.query(OrganizationMember).filter(
        OrganizationMember.organization_id == org.id,
        OrganizationMember.user_id == user.id
    ).first()
    
    if not member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a member of the organization"
        )
    
    return member


def generate_unique_slug(
    name: str,
    organization_id: UUID,
    db: Session
) -> str:
    """生成唯一的 slug"""
    import re
    from uuid import uuid4
    
    # 将名称转换为 slug 格式
    slug = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')
    
    # 检查是否已存在
    existing = db.query(Project).filter(
        Project.slug == slug,
        Project.organization_id == organization_id
    ).first()
    
    if existing:
        # 添加随机后缀
        slug = f"{slug}-{uuid4().hex[:6]}"
    
    return slug


# ==================== API 端点 ====================

@router.get("", response_model=ProjectListResponse)
async def list_projects(
    current_user: User = Depends(require_auth),
    db: Session = Depends(get_db),
    organization_id: Optional[str] = None,
    page: int = 1,
    page_size: int = settings.DEFAULT_PAGE_SIZE
):
    """
    获取项目列表
    
    可按组织 ID 过滤
    """
    page_size = min(page_size, settings.MAX_PAGE_SIZE)
    offset = (page - 1) * page_size
    
    # 获取用户所属组织
    org_members = db.query(OrganizationMember).filter(
        OrganizationMember.user_id == current_user.id
    ).all()
    org_ids = [str(m.organization_id) for m in org_members]
    
    # 构建查询
    from sqlalchemy import func
    query = db.query(Project).filter(
        Project.organization_id.in_(org_ids)
    )
    
    if organization_id:
        if organization_id not in org_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not a member of this organization"
            )
        query = query.filter(Project.organization_id == organization_id)
    
    total = query.count()
    projects = query.offset(offset).limit(page_size).all()
    
    # 获取每个项目的环境数量
    items = []
    for project in projects:
        env_count = db.query(Environment).filter(
            Environment.project_id == project.id
        ).count()
        
        items.append(ProjectResponse(
            id=str(project.id),
            name=project.name,
            slug=project.slug,
            description=project.description,
            organization_id=str(project.organization_id),
            owner_id=str(project.owner_id),
            status=project.status,
            created_at=project.created_at,
            updated_at=project.updated_at,
            environment_count=env_count
        ))
    
    return ProjectListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size
    )


@router.post("", response_model=ProjectResponse)
async def create_project(
    request: ProjectCreateRequest,
    current_user: User = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """
    创建新项目
    
    需要是组织成员
    """
    # 验证组织 ID
    try:
        org_uuid = UUID(request.organization_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid organization ID format"
        )
    
    # 检查组织权限
    org = db.query(Organization).filter(Organization.id == org_uuid).first()
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found"
        )
    
    check_project_permission(org, current_user, db)
    
    # 检查项目名是否已存在
    existing = db.query(Project).filter(
        Project.name == request.name,
        Project.organization_id == org_uuid
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Project name already exists in this organization"
        )
    
    # 生成 slug
    slug = request.slug or generate_unique_slug(request.name, org_uuid, db)
    
    # 创建项目
    project = Project(
        name=request.name,
        slug=slug,
        description=request.description,
        organization_id=org_uuid,
        owner_id=current_user.id,
        sensitivity="internal",
        status="active"
    )
    
    db.add(project)
    db.commit()
    db.refresh(project)
    
    # 创建默认环境 (development)
    default_env = Environment(
        name="development",
        description="Development environment",
        project_id=project.id,
        config={}
    )
    db.add(default_env)
    db.commit()
    
    return ProjectResponse(
        id=str(project.id),
        name=project.name,
        slug=project.slug,
        description=project.description,
        organization_id=str(project.organization_id),
        owner_id=str(project.owner_id),
        status=project.status,
        created_at=project.created_at,
        updated_at=project.updated_at,
        environment_count=1
    )


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: str,
    current_user: User = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """
    获取项目详情
    """
    project = get_project_or_404(project_id, db)
    
    # 获取组织并检查权限
    org = db.query(Organization).filter(Organization.id == project.organization_id).first()
    check_project_permission(org, current_user, db)
    
    # 获取环境数量
    env_count = db.query(Environment).filter(
        Environment.project_id == project.id
    ).count()
    
    return ProjectResponse(
        id=str(project.id),
        name=project.name,
        slug=project.slug,
        description=project.description,
        organization_id=str(project.organization_id),
        owner_id=str(project.owner_id),
        status=project.status,
        created_at=project.created_at,
        updated_at=project.updated_at,
        environment_count=env_count
    )


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: str,
    request: ProjectUpdateRequest,
    current_user: User = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """
    更新项目信息
    
    需要组织 admin 或 owner 权限
    """
    project = get_project_or_404(project_id, db)
    
    # 获取组织并检查权限
    org = db.query(Organization).filter(Organization.id == project.organization_id).first()
    member = check_project_permission(org, current_user, db)
    if member.role not in ["owner", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions"
        )
    
    # 更新字段
    if request.name is not None:
        project.name = request.name
    if request.description is not None:
        project.description = request.description
    if request.status is not None:
        project.status = request.status.value
    
    db.commit()
    db.refresh(project)
    
    env_count = db.query(Environment).filter(
        Environment.project_id == project.id
    ).count()
    
    return ProjectResponse(
        id=str(project.id),
        name=project.name,
        slug=project.slug,
        description=project.description,
        organization_id=str(project.organization_id),
        owner_id=str(project.owner_id),
        status=project.status,
        created_at=project.created_at,
        updated_at=project.updated_at,
        environment_count=env_count
    )


@router.delete("/{project_id}")
async def delete_project(
    project_id: str,
    current_user: User = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """
    删除项目 (软删除)
    
    需要组织 owner 权限
    """
    project = get_project_or_404(project_id, db)
    
    # 获取组织并检查权限
    org = db.query(Organization).filter(Organization.id == project.organization_id).first()
    member = check_project_permission(org, current_user, db)
    if member.role != "owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only organization owner can delete projects"
        )
    
    # 软删除
    project.status = "archived"
    
    db.commit()
    
    return {"message": "Project archived successfully"}


# ==================== 环境管理 ====================

@router.get("/{project_id}/environments", response_model=List[EnvironmentResponse])
async def list_environments(
    project_id: str,
    current_user: User = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """
    获取项目环境列表
    """
    project = get_project_or_404(project_id, db)
    
    # 获取组织并检查权限
    org = db.query(Organization).filter(Organization.id == project.organization_id).first()
    check_project_permission(org, current_user, db)
    
    environments = db.query(Environment).filter(
        Environment.project_id == project.id
    ).all()
    
    return [
        EnvironmentResponse(
            id=str(env.id),
            name=env.name,
            description=env.description,
            project_id=str(env.project_id),
            config=env.config,
            created_at=env.created_at,
            updated_at=env.updated_at
        )
        for env in environments
    ]


@router.post("/{project_id}/environments", response_model=EnvironmentResponse)
async def create_environment(
    project_id: str,
    request: EnvironmentCreateRequest,
    current_user: User = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """
    创建项目环境
    
    需要组织 admin 或 owner 权限
    """
    project = get_project_or_404(project_id, db)
    
    # 获取组织并检查权限
    org = db.query(Organization).filter(Organization.id == project.organization_id).first()
    member = check_project_permission(org, current_user, db)
    
    if member.role not in ["owner", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions"
        )
    
    # 检查环境名是否已存在
    existing = db.query(Environment).filter(
        Environment.name == request.name,
        Environment.project_id == project.id
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Environment name already exists"
        )
    
    env = Environment(
        name=request.name,
        description=request.description,
        project_id=project.id,
        config=request.config or {}
    )
    
    db.add(env)
    db.commit()
    db.refresh(env)
    
    return EnvironmentResponse(
        id=str(env.id),
        name=env.name,
        description=env.description,
        project_id=str(env.project_id),
        config=env.config,
        created_at=env.created_at,
        updated_at=env.updated_at
    )