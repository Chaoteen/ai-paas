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
from sqlalchemy.orm import Session, sessionmaker

from main import app
from models.base import Base
from models.database import get_db
from models.auth import APIKey, Organization, OrganizationMember, User
from models.project import Environment, Integration, Project
from models.agent import Agent
from models.conversation import Conversation, Feedback, Message
from models.abac import ABACPolicy, PolicyAssignment, PolicyEvaluationLog
from models.audit import AuditLog, FeatureFlag, SystemSetting
from models.billing import Quota, UsageRecord
from models.prompt import PromptTemplate, TemplateVersion
from services.auth_service import create_access_token, hash_password

from persistence.db import Database
from persistence.models import Base as PersistenceBase
from persistence.settings import PostgresSettings


def _env(name: str, default: str | None = None) -> str:
    v = os.getenv(name, default)
    if v is None or v == "":
        raise RuntimeError(f"Missing env var: {name}")
    return v


@pytest.fixture(scope="session")
def base_url() -> str:
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
    with httpx.Client(base_url=base_url, timeout=10.0) as client:
        yield client


TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://postgres:postgres@localhost:5432/ai_paas_test",
)


@pytest.fixture(scope="session")
def test_engine():
    engine = create_engine(
        TEST_DATABASE_URL,
        echo=False,
        future=True,
    )

    # 根修：每次测试会话开始前，强制清空旧 schema，再按当前 metadata 重建。
    # 仅 create_all() 不会修正已存在表的列类型，容易残留历史 varchar/uuid 不一致问题。
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    yield engine

    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture
def db_session(test_engine) -> Generator[Session, None, None]:
    connection = test_engine.connect()
    transaction = connection.begin()
    SessionLocal = sessionmaker(bind=connection, expire_on_commit=False)
    session = SessionLocal()

    try:
        yield session
    finally:
        try:
            if session.in_transaction():
                session.rollback()
        finally:
            session.close()

        if transaction.is_active:
            transaction.rollback()

        connection.close()


@pytest_asyncio.fixture
async def pg_async_db():
    settings = PostgresSettings(
        host=os.getenv("TEST_POSTGRES_HOST", "127.0.0.1"),
        port=int(os.getenv("TEST_POSTGRES_PORT", "5432")),
        database=os.getenv("TEST_POSTGRES_DB", "ai_paas_test"),
        user=os.getenv("TEST_POSTGRES_USER", "postgres"),
        password=os.getenv("TEST_POSTGRES_PASSWORD", "postgres"),
        echo=False,
    )
    database = Database(settings)

    async with database.engine.begin() as conn:
        await conn.run_sync(PersistenceBase.metadata.create_all)

    async with database.session() as session:
        for table_name in ["data_events", "control_events", "agents"]:
            await session.execute(
                text(f"TRUNCATE TABLE {table_name} RESTART IDENTITY CASCADE")
            )

    yield database
    await database.dispose()


@pytest.fixture
def test_user(db_session: Session) -> User:
    user = User(
        id=uuid.uuid4(),
        email="test@example.com",
        username="testuser",
        password_hash="$2b$12$test_hash_placeholder",
        status="active",
        role="developer",
        department="Engineering",
        level="L5",
        auth_level="basic",
        abac_attributes={"clearance": "internal"},
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def test_organization(db_session: Session, test_user: User) -> Organization:
    org = Organization(
        id=uuid.uuid4(),
        name="Test Organization",
        slug="test-org",
        owner_id=test_user.id,
        plan="free",
        sensitivity_default="internal",
        compliance_tags=["SOC2"],
        allowed_locations=["US", "CN"],
        data_residency="US",
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
    project = Project(
        id=uuid.uuid4(),
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
    agent = Agent(
        id=uuid.uuid4(),
        project_id=test_project.id,
        organization_id=test_project.organization_id,
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
    policy = ABACPolicy(
        id=uuid.uuid4(),
        name="Test Access Policy",
        description="Test policy for development",
        effect="allow",
        subject_conditions={"role": ["developer", "admin"]},
        resource_conditions={"sensitivity": ["internal", "public"]},
        environment_conditions={},
        actions=["read", "write"],
        priority=1,
        is_active=True,
    )
    db_session.add(policy)
    db_session.commit()
    db_session.refresh(policy)
    return policy


@pytest.fixture
def api_client(db_session: Session) -> Generator[TestClient, None, None]:
    user = User(
        id=uuid.uuid4(),
        email="apitest@example.com",
        username="apitestuser",
        password_hash=hash_password("apitest123"),
        status="active",
        role="developer",
        department="Engineering",
        level="L5",
        auth_level="basic",
        abac_attributes={"clearance": "internal"},
    )
    db_session.add(user)
    db_session.flush()

    org = Organization(
        id=uuid.uuid4(),
        name="API Test Organization",
        slug="api-test-org",
        owner_id=user.id,
        plan="free",
        sensitivity_default="internal",
        compliance_tags=["SOC2"],
        allowed_locations=["US", "CN"],
        data_residency="US",
    )
    db_session.add(org)
    db_session.flush()

    member = OrganizationMember(
        id=uuid.uuid4(),
        organization_id=org.id,
        user_id=user.id,
        role="owner",
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
    db_session: Session,
) -> tuple[TestClient, User, Organization]:
    login_response = api_client.post(
        "/api/v1/auth/login/json",
        json={
            "email": "apitest@example.com",
            "password": "apitest123",
        },
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
    db_session: Session,
) -> tuple[TestClient, User, Organization]:
    admin_user = User(
        id=uuid.uuid4(),
        email="admin@example.com",
        username="adminuser",
        password_hash=hash_password("admin123"),
        status="active",
        role="admin",
        department="Engineering",
        level="L7",
        auth_level="high",
        abac_attributes={"clearance": "confidential"},
    )
    db_session.add(admin_user)
    db_session.flush()

    admin_org = Organization(
        id=uuid.uuid4(),
        name="Admin Test Organization",
        slug="admin-test-org",
        owner_id=admin_user.id,
        plan="enterprise",
        sensitivity_default="confidential",
        compliance_tags=["SOC2", "ISO27001"],
        allowed_locations=["US", "CN", "EU"],
        data_residency="US",
    )
    db_session.add(admin_org)
    db_session.flush()

    admin_member = OrganizationMember(
        id=uuid.uuid4(),
        organization_id=admin_org.id,
        user_id=admin_user.id,
        role="owner",
    )
    db_session.add(admin_member)
    db_session.commit()

    login_response = api_client.post(
        "/api/v1/auth/login/json",
        json={
            "email": "admin@example.com",
            "password": "admin123",
        },
    )

    if login_response.status_code == 200:
        token = login_response.json()["access_token"]
        api_client.headers.update({"Authorization": f"Bearer {token}"})

    return api_client, admin_user, admin_org


@pytest.fixture
def test_config() -> dict:
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
    return create_access_token(
        subject=test_user.email,
        user_id=test_user.id,
        role=test_user.role,
        expires_delta=timedelta(minutes=60),
    )