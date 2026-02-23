"""
项目管理 API 测试
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from models.auth import User, Organization, OrganizationMember
from models.project import Project, Environment
from services.auth_service import hash_password


@pytest.fixture
def project_client(api_client: TestClient, db_session: Session):
    """创建带项目的测试客户端"""
    # 创建用户和组织
    user = User(
        email="projtest@example.com",
        username="projtestuser",
        status="active",
        password_hash=hash_password("password123"),
        role="user"
    )
    db_session.add(user)
    db_session.flush()
    
    org = Organization(
        name="Project Test Org",
        slug="project-test-org",
        owner_id=user.id
    )
    db_session.add(org)
    db_session.flush()
    
    member = OrganizationMember(
        organization_id=org.id,
        user_id=user.id,
        role="owner"
    )
    db_session.add(member)
    db_session.commit()
    
    # 创建项目
    project = Project(
        name="Test Project",
        slug="test-project",
        description="Test description",
        organization_id=org.id,
        owner_id=user.id,
        status="active"
    )
    db_session.add(project)
    db_session.commit()
    
    # 登录
    login_response = api_client.post(
        "/api/v1/auth/login/json",
        json={"email": "projtest@example.com", "password": "password123"}
    )
    token = login_response.json()["access_token"]
    api_client.headers = {"Authorization": f"Bearer {token}"}
    
    return api_client, user, org, project


class TestProjectCRUD:
    """项目 CRUD 测试"""
    
    def test_list_projects(self, project_client):
        """测试获取项目列表"""
        api_client, user, org, project = project_client
        response = api_client.get("/api/v1/projects")
        
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert len(data["items"]) >= 1
    
    def test_create_project(self, project_client):
        """测试创建项目"""
        api_client, user, org, project = project_client
        response = api_client.post(
            "/api/v1/projects",
            json={
                "name": "New Project",
                "description": "New project description",
                "organization_id": str(org.id)
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "New Project"
        assert "slug" in data
    
    def test_get_project(self, project_client):
        """测试获取项目详情"""
        api_client, user, org, project = project_client
        response = api_client.get(f"/api/v1/projects/{project.id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(project.id)
    
    def test_update_project(self, project_client):
        """测试更新项目"""
        api_client, user, org, project = project_client
        response = api_client.put(
            f"/api/v1/projects/{project.id}",
            json={"name": "Updated Project"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Project"
    
    def test_delete_project(self, project_client):
        """测试删除项目"""
        api_client, user, org, project = project_client
        response = api_client.delete(f"/api/v1/projects/{project.id}")
        
        assert response.status_code == 200
    
    def test_project_not_found(self, project_client):
        """测试项目不存在"""
        api_client, user, org, project = project_client
        from uuid import uuid4
        response = api_client.get(f"/api/v1/projects/{uuid4()}")
        
        assert response.status_code == 404


class TestEnvironmentCRUD:
    """环境管理测试"""
    
    def test_list_environments(self, project_client):
        """测试获取环境列表"""
        api_client, user, org, project = project_client
        response = api_client.get(f"/api/v1/projects/{project.id}/environments")
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
    
    def test_create_environment(self, project_client):
        """测试创建环境"""
        api_client, user, org, project = project_client
        response = api_client.post(
            f"/api/v1/projects/{project.id}/environments",
            json={
                "name": "staging",
                "description": "Staging environment",
                "config": {"debug": True}
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "staging"
    
    def test_duplicate_environment_name(self, project_client):
        """测试重复环境名"""
        api_client, user, org, project = project_client
        # 创建第一个
        api_client.post(
            f"/api/v1/projects/{project.id}/environments",
            json={"name": "production"}
        )
        # 尝试创建重复的
        response = api_client.post(
            f"/api/v1/projects/{project.id}/environments",
            json={"name": "production"}
        )
        
        assert response.status_code == 400