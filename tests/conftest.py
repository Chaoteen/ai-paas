import os
import uuid
import pytest
import httpx
import uuid
def _env(name: str, default: str | None = None) -> str:
    v = os.getenv(name, default)
    if v is None or v == "":
        raise RuntimeError(f"Missing env var: {name}")
    return v

@pytest.fixture(scope="session")
def base_url() -> str:
    return _env("AI_PAAS_BASE_URL")

@pytest.fixture(scope="session")
def tenant_a() -> str:
    return os.getenv("AI_PAAS_TENANT_A", "tenant_a")

@pytest.fixture(scope="session")
def tenant_b() -> str:
    return os.getenv("AI_PAAS_TENANT_B", "tenant_b")

@pytest.fixture(scope="session")
def token_tenant_a_admin() -> str:
    return _env("AI_PAAS_TOKEN_TENANT_A_ADMIN")

@pytest.fixture(scope="session")
def token_tenant_b_user() -> str:
    return _env("AI_PAAS_TOKEN_TENANT_B_USER")

@pytest.fixture
def client(base_url: str) -> httpx.Client:
    return httpx.Client(base_url=base_url, timeout=10.0)
# ========== 以下内容为新增 ==========

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from typing import Generator

# 导入所有模型
from models.base import Base
from models.auth import User, Organization, OrganizationMember, APIKey
from models.project import Project, Environment, Integration
from models.agent import Agent, Tool, WorkflowNode, WorkflowEdge
from models.conversation import Conversation, Message, Feedback
from models.abac import ABACPolicy, PolicyAssignment, PolicyEvaluationLog
from models.audit import AuditLog, SystemSetting, FeatureFlag
from models.billing import UsageRecord, Quota
from models.prompt import PromptTemplate, TemplateVersion

# 测试数据库配置
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+psycopg2://postgres:postgres@localhost:5432/ai_paas_test"
)


@pytest.fixture(scope="session")
def test_engine():
    """创建测试数据库引擎"""
    engine = create_engine(
        TEST_DATABASE_URL,
        poolclass=StaticPool,
        echo=False,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session(test_engine) -> Generator[Session, None, None]:
    """创建数据库会话 fixture"""
    connection = test_engine.connect()
    transaction = connection.begin()
    SessionLocal = sessionmaker(bind=connection, expire_on_commit=False)
    session = SessionLocal()
    
    try:
        yield session
    finally:
        transaction.rollback()
        session.close()
        connection.close()


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
def test_project(db_session: Session, test_organization: Organization, test_user: User) -> Project:
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
        environment_conditions={"time_range": "business_hours"},
        priority=1,
        is_active=True
    )
    db_session.add(policy)
    db_session.commit()
    db_session.refresh(policy)
    return policy