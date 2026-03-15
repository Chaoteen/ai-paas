"""
AI-PaaS 平台测试配置
包含：
1. 外部服务测试
2. 本地 FastAPI API 测试
3. 现有业务模型同步数据库 Fixture
4. PostgreSQL Persistence 异步数据库 Fixture
"""

import os
import uuid
from datetime import timedelta
from typing import Generator

import httpx
import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session

from main import app
from models.base import Base
from models.database import get_db
from models.auth import User, Organization, OrganizationMember, APIKey
from models.project import Project, Environment, Integration
from models.agent import Agent
from models.conversation import Conversation, Message, Feedback
from models.abac import ABACPolicy, PolicyAssignment, PolicyEvaluationLog
from models.audit import AuditLog, SystemSetting, FeatureFlag
from models.billing import UsageRecord, Quota
from models.prompt import PromptTemplate, TemplateVersion
from services.auth_service import hash_password, create_access_token

from persistence.db import Database
from persistence.settings import PostgresSettings
from persistence.models import Base as PersistenceBase


# ==================== 环境变量辅助函数 ====================

def _env(name: str, default: str | None = None) -> str:
    v = os.getenv(name, default)
    if v is None or v == "":
        raise RuntimeError(f"Missing env var: {name}")
    return v


# ==================== 外部服务测试 Fixture ====================

@pytest.fixture(scope="session")
def base_url() -> str:
    """外部服务基础 URL"""
    return os.getenv("AI_PAAS_BASE_URL", "http://localhost:8000")


@pytest.fixture(scope="session")
def tenant_a() -> str:
    return os.getenv("AI_PAAS_TENANT_A", "tenant_a")


@pytest.fixture(scope="session")
def tenant_b() -> str:
    return os.getenv("AI_PAAS_TENANT_B", "tenant_b")


@pytest.fixture(scope="session")
def token_tenant_a_admin() -> str:
    return os.getenv("AI_PAAS_TOKEN_TENANT_A_ADMIN", "")


@pytest.fixture(scope="session")
def token_tenant_b_user() -> str:
    return os.getenv("AI_PAAS_TOKEN_TENANT_B_USER", "")


@pytest.fixture
def external_client(base_url: str) -> Generator[httpx.Client, None, None]:
    """外部服务测试客户端（httpx）"""
    with httpx.Client(base_url=base_url, timeout=10.0) as client:
        yield client


# ==================== 现有同步测试数据库配置 ====================
# 这部分给你原来的 ORM / FastAPI / 业务模型测试继续使用

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://postgres:postgres@localhost:5432/ai_paas_test"
)


@pytest.fixture(scope="session")
def test_engine():
    """
    创建同步测试数据库引擎
    用于现有 models/* 和 FastAPI TestClient 测试
    """
    engine = create_engine(
        TEST_DATABASE_URL,
        echo=False,
        future=True,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session(test_engine) -> Generator[Session, None, None]:
    """
    创建数据库会话 fixture（每个测试自动回滚）
    用于现有同步 ORM 测试
    """
    connection = test_engine.connect()
    transaction = connection.begin()
    SessionLocal = sessionmaker(bind=connection, expire_on_commit=False)
    session = SessionLocal()

    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


# ==================== PostgreSQL Persistence 异步数据库 Fixture ====================
# 这部分专门给你新加的 persistence / postgres repository 测试使用

@pytest_asyncio.fixture
async def pg_async_db():
    """
    异步 PostgreSQL 数据库 fixture
    用于：
    - PostgresAgentRepository
    - PostgresControlEventRepository
    - PostgresDataEventRepository
    """
    settings = PostgresSettings(
        host=os.getenv("TEST_POSTGRES_HOST", "127.0.0.1"),
        port=int(os.getenv("TEST_POSTGRES_PORT", "5432")),
        database=os.getenv("TEST_POSTGRES_DB", "ai_paas_test"),
        user=os.getenv("TEST_POSTGRES_USER", "postgres"),
        password=os.getenv("TEST_POSTGRES_PASSWORD", "postgres"),
        echo=False,
    )
    database = Database(settings)

    # 先自动建表，确保 persistence.models 里的表都存在
    async with database.engine.begin() as conn:
        await conn.run_sync(PersistenceBase.metadata.create_all)

    # 再清空表，保证每个测试干净
    async with database.session() as session:
        for table_name in ["data_events", "control_events", "agents"]:
            await session.execute(
                text(f"TRUNCATE TABLE {table_name} RESTART IDENTITY CASCADE")
            )

    yield database
    await database.dispose()


# ==================== 测试数据 Fixture ====================

@pytest.fixture
def test_user(db_session: Session) -> User:
    """创建测试用户"""
    user = User(
        id=str(uuid.uuid4()),
        email="test@example.com",
        username="testuser",
        password_hash="$2b$12$test_hash_placeholder",
        status="active",
        role="developer",
        department="Engineering",
        level="L5",
        auth_level="basic",
        abac_attributes={"clearance": "internal"}
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def test_organization(db_session: Session, test_user: User) -> Organization:
    """创建测试组织"""
    org = Organization(
        id=str(uuid.uuid4()),
        name="Test Organization",
        slug="test-org",
        owner_id=test_user.id,
        plan="free",
        sensitivity_default="internal",
        compliance_tags=["SOC2"],
        allowed_locations=["US", "CN"],
        data_residency="US"
    )
    db_session.add(org)
    db_session.commit()
    db_session.refresh(org)
    return org


@pytest.fixture
def test_project(
    db_session: Session,
    test_organization: Organization,
    test_user: User,
) -> Project:
    """创建测试项目"""
    project = Project(
        id=str(uuid.uuid4()),
        organization_id=test_organization.id,
        name="Test Project",
        slug="test-project",
        sensitivity="internal",
        owner_id=test_user.id,
    )
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)
    return project


@pytest.fixture
def test_agent(db_session: Session, test_project: Project, test_user: User) -> Agent:
    """创建测试 Agent"""
    agent = Agent(
        id=str(uuid.uuid4()),
        project_id=test_project.id,
        name="Test Agent",
        slug="test-agent",
        agent_type="chat",
        model_provider="openai",
        model_name="gpt-4",
        sensitivity="internal",
        owner_id=test_user.id,
        tags=["test", "demo"],
    )
    db_session.add(agent)
    db_session.commit()
    db_session.refresh(agent)
    return agent


@pytest.fixture
def test_abac_policy(db_session: Session) -> ABACPolicy:
    """创建测试 ABAC 策略"""
    policy = ABACPolicy(
        id=str(uuid.uuid4()),
        name="Test Access Policy",
        description="Test policy for development",
        effect="allow",
        subject_conditions={"role": ["developer", "admin"]},
        resource_conditions={"sensitivity": ["internal", "public"]},
        environment_conditions={},
        actions=["read", "write"],
        priority=1,
        is_active=True
    )
    db_session.add(policy)
    db_session.commit()
    db_session.refresh(policy)
    return policy


# ==================== FastAPI 本地 API 测试 Fixture ====================

@pytest.fixture
def api_client(db_session: Session) -> Generator[TestClient, None, None]:
    """
    FastAPI 本地 API 测试客户端
    使用同步测试数据库会话，覆盖 get_db
    """
    # 创建测试用户和组织
    user = User(
        id=str(uuid.uuid4()),
        email="apitest@example.com",
        username="apitestuser",
        password_hash=hash_password("apitest123"),
        status="active",
        role="developer",
        department="Engineering",
        level="L5",
        auth_level="basic",
        abac_attributes={"clearance": "internal"}
    )
    db_session.add(user)
    db_session.flush()

    org = Organization(
        id=str(uuid.uuid4()),
        name="API Test Organization",
        slug="api-test-org",
        owner_id=user.id,
        plan="free",
        sensitivity_default="internal",
        compliance_tags=["SOC2"],
        allowed_locations=["US", "CN"],
        data_residency="US"
    )
    db_session.add(org)
    db_session.flush()

    member = OrganizationMember(
        id=str(uuid.uuid4()),
        organization_id=org.id,
        user_id=user.id,
        role="owner"
    )
    db_session.add(member)
    db_session.commit()

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()


@pytest.fixture
def authenticated_api_client(
    api_client: TestClient,
    db_session: Session
) -> tuple[TestClient, User, Organization]:
    """
    已认证的 API 测试客户端
    返回：(client, user, organization)
    """
    login_response = api_client.post(
        "/api/v1/auth/login/json",
        json={
            "email": "apitest@example.com",
            "password": "apitest123"
        }
    )

    if login_response.status_code == 200:
        token = login_response.json()["access_token"]
        api_client.headers.update({"Authorization": f"Bearer {token}"})

    user = db_session.query(User).filter(User.email == "apitest@example.com").first()
    org = db_session.query(Organization).filter(
        Organization.name == "API Test Organization"
    ).first()

    return api_client, user, org


@pytest.fixture
def admin_api_client(
    api_client: TestClient,
    db_session: Session
) -> tuple[TestClient, User, Organization]:
    """
    管理员 API 测试客户端
    """
    admin_user = User(
        id=str(uuid.uuid4()),
        email="admin@example.com",
        username="adminuser",
        password_hash=hash_password("admin123"),
        status="active",
        role="admin",
        department="Engineering",
        level="L7",
        auth_level="high",
        abac_attributes={"clearance": "confidential"}
    )
    db_session.add(admin_user)
    db_session.flush()

    admin_org = Organization(
        id=str(uuid.uuid4()),
        name="Admin Test Organization",
        slug="admin-test-org",
        owner_id=admin_user.id,
        plan="enterprise",
        sensitivity_default="confidential",
        compliance_tags=["SOC2", "ISO27001"],
        allowed_locations=["US", "CN", "EU"],
        data_residency="US"
    )
    db_session.add(admin_org)
    db_session.flush()

    admin_member = OrganizationMember(
        id=str(uuid.uuid4()),
        organization_id=admin_org.id,
        user_id=admin_user.id,
        role="owner"
    )
    db_session.add(admin_member)
    db_session.commit()

    login_response = api_client.post(
        "/api/v1/auth/login/json",
        json={
            "email": "admin@example.com",
            "password": "admin123"
        }
    )

    if login_response.status_code == 200:
        token = login_response.json()["access_token"]
        api_client.headers.update({"Authorization": f"Bearer {token}"})

    return api_client, admin_user, admin_org


# ==================== 测试辅助 Fixture ====================

@pytest.fixture
def test_config() -> dict:
    """测试配置"""
    return {
        "test_email": "test@example.com",
        "test_password": "testpassword123",
        "api_test_email": "apitest@example.com",
        "api_test_password": "apitest123",
        "admin_email": "admin@example.com",
        "admin_password": "admin123",
    }


@pytest.fixture
def sample_jwt_token(test_user: User) -> str:
    """生成示例 JWT 令牌"""
    return create_access_token(
        subject=test_user.email,
        user_id=test_user.id,
        role=test_user.role,
        expires_delta=timedelta(minutes=60)
    )