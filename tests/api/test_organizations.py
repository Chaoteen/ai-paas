"""
组织管理 API 测试
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from models.auth import User, Organization, OrganizationMember
from services.auth_service import hash_password


@pytest.fixture
def authenticated_client(api_client: TestClient, db_session: Session):
    """创建已认证的测试客户端"""
    # 创建测试用户
    user = User(
        email="orgtest@example.com",
        username="orgtestuser",
        password_hash=hash_password("password123"),
        role="user",
        status="active"
    )
    db_session.add(user)
    db_session.flush()

    # 创建组织（添加 slug）
    org = Organization(
        name="Test Org",
        slug="test-org",
        owner_id=user.id
    )
    db_session.add(org)
    db_session.flush()

    # 创建成员关系
    member = OrganizationMember(
        organization_id=org.id,
        user_id=user.id,
        role="owner"
    )
    db_session.add(member)
    db_session.commit()

    # 登录获取令牌
    login_response = api_client.post(
        "/api/v1/auth/login/json",
        json={"email": "orgtest@example.com", "password": "password123"}
    )
    token = login_response.json()["access_token"]

    api_client.headers = {"Authorization": f"Bearer {token}"}
    return api_client, user, org


class TestOrganizationCRUD:
    """组织 CRUD 测试"""
    
    def test_list_organizations(self, authenticated_client):
        """测试获取组织列表"""
        api_client, user, org = authenticated_client
        response = api_client.get("/api/v1/organizations")
        
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert len(data["items"]) >= 1
    
    def test_create_organization(self, authenticated_client):
        """测试创建组织"""
        api_client, user, org = authenticated_client
        response = api_client.post(
            "/api/v1/organizations",
            json={
                "name": "New Organization",
                "description": "Test description"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "New Organization"
        assert "id" in data
    
    def test_get_organization(self, authenticated_client):
        """测试获取组织详情"""
        api_client, user, org = authenticated_client
        response = api_client.get(f"/api/v1/organizations/{org.id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(org.id)
        assert data["name"] == "Test Org"
    
    def test_update_organization(self, authenticated_client):
        """测试更新组织"""
        api_client, user, org = authenticated_client
        response = api_client.put(
            f"/api/v1/organizations/{org.id}",
            json={"name": "Updated Org Name"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Org Name"
    
    def test_delete_organization(self, authenticated_client):
        """测试删除组织"""
        api_client, user, org = authenticated_client
        response = api_client.delete(f"/api/v1/organizations/{org.id}")
        
        assert response.status_code == 200
    
    def test_organization_not_found(self, authenticated_client):
        """测试组织不存在"""
        api_client, user, org = authenticated_client
        from uuid import uuid4
        response = api_client.get(f"/api/v1/organizations/{uuid4()}")
        
        assert response.status_code == 404
    
    def test_unauthorized_access(self, api_client: TestClient):
        """测试未授权访问"""
        response = api_client.get("/api/v1/organizations")
        assert response.status_code == 401


class TestOrganizationMembers:
    """组织成员管理测试"""
    
    def test_list_members(self, authenticated_client):
        """测试获取成员列表"""
        api_client, user, org = authenticated_client
        response = api_client.get(f"/api/v1/organizations/{org.id}/members")
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
    
    def test_add_member(self, authenticated_client, db_session: Session):
        """测试添加成员"""
        api_client, user, org = authenticated_client
        
        # 创建新用户
        new_user = User(
            email="newmember@example.com",
            username="newmember",
            status="active",
            password_hash=hash_password("password123"),
            role="user"
        )
        db_session.add(new_user)
        db_session.commit()
        
        response = api_client.post(
            f"/api/v1/organizations/{org.id}/members",
            json={
                "user_email": "newmember@example.com",
                "role": "member"
            }
        )
        
        assert response.status_code == 200
    
    def test_remove_member(self, authenticated_client, db_session: Session):
        """测试移除成员"""
        api_client, user, org = authenticated_client
        
        # 创建并添加成员
        new_user = User(
            email="toremove@example.com",
            username="toremove",
            status="active",
            password_hash=hash_password("password123"),
            role="user"
        )
        db_session.add(new_user)
        db_session.flush()
        
        member = OrganizationMember(
            organization_id=org.id,
            user_id=new_user.id,
            role="member"
        )
        db_session.add(member)
        db_session.commit()
        
        response = api_client.delete(
            f"/api/v1/organizations/{org.id}/members/{new_user.id}"
        )
        
        assert response.status_code == 200
    
    def test_cannot_remove_owner(self, authenticated_client):
        """测试不能移除 owner"""
        api_client, user, org = authenticated_client
        response = api_client.delete(
            f"/api/v1/organizations/{org.id}/members/{user.id}"
        )
        
        assert response.status_code == 400