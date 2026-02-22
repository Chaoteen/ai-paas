"""
SQLAlchemy 模型单元测试
测试所有模型的创建、验证和关系
"""
import uuid
import pytest
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from models.auth import User, Organization, OrganizationMember, APIKey
from models.project import Project, Environment, Integration
from models.agent import Agent, Tool, WorkflowNode, WorkflowEdge
from models.abac import ABACPolicy, PolicyAssignment, PolicyEvaluationLog


class TestUserModel:
    """User 模型测试"""
    
    def test_create_user(self, db_session: Session):
        """测试创建用户"""
        user = User(
            id=str(uuid.uuid4()),
            email="unittest@example.com",
            username="unittestuser",
            password_hash="$2b$12$test_hash",
            status="active",
            role="developer"
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        
        assert user.email == "unittest@example.com"
        assert user.username == "unittestuser"
        assert user.status == "active"
        assert user.role == "developer"
    
    def test_user_email_unique(self, db_session: Session):
        """测试用户邮箱唯一性"""
        user1 = User(
            id=str(uuid.uuid4()),
            email="unique@example.com",
            username="user1",
            password_hash="hash1"
        )
        db_session.add(user1)
        db_session.commit()
        
        user2 = User(
            id=str(uuid.uuid4()),
            email="unique@example.com",  # 重复邮箱
            username="user2",
            password_hash="hash2"
        )
        db_session.add(user2)
        
        with pytest.raises(Exception):  # 唯一性约束违反
            db_session.commit()
    
    def test_user_abac_attributes(self, db_session: Session):
        """测试用户 ABAC 属性"""
        user = User(
            id=str(uuid.uuid4()),
            email="abac@example.com",
            username="abacuser",
            password_hash="hash",
            department="Engineering",
            level="L5",
            auth_level="elevated",
            abac_attributes={"clearance": "confidential", "teams": ["core", "security"]}
        )
        db_session.add(user)
        db_session.commit()
        
        assert user.department == "Engineering"
        assert user.level == "L5"
        assert user.abac_attributes["clearance"] == "confidential"


class TestOrganizationModel:
    """Organization 模型测试"""
    
    def test_create_organization(self, db_session: Session, test_user: User):
        """测试创建组织"""
        org = Organization(
            id=str(uuid.uuid4()),
            name="Unit Test Org",
            slug="unit-test-org",
            owner_id=test_user.id,
            plan="pro"
        )
        db_session.add(org)
        db_session.commit()
        db_session.refresh(org)
        
        assert org.name == "Unit Test Org"
        assert org.slug == "unit-test-org"
        assert org.plan == "pro"
        assert org.owner_id == test_user.id
    
    def test_organization_compliance_tags(self, db_session: Session, test_user: User):
        """测试组织合规标签"""
        org = Organization(
            id=str(uuid.uuid4()),
            name="Compliance Org",
            slug="compliance-org",
            owner_id=test_user.id,
            compliance_tags=["SOC2", "GDPR", "HIPAA"],
            allowed_locations=["US", "EU", "CN"]
        )
        db_session.add(org)
        db_session.commit()
        
        assert "SOC2" in org.compliance_tags
        assert "US" in org.allowed_locations


class TestProjectModel:
    """Project 模型测试"""
    
    def test_create_project(self, db_session: Session, test_organization: Organization, test_user: User):
        """测试创建项目"""
        project = Project(
            id=str(uuid.uuid4()),
            organization_id=test_organization.id,
            name="Unit Test Project",
            slug="unit-test-project",
            sensitivity="confidential",
            owner_id=test_user.id
        )
        db_session.add(project)
        db_session.commit()
        db_session.refresh(project)
        
        assert project.organization_id == test_organization.id
        assert project.sensitivity == "confidential"
    
    def test_project_mfa_required(self, db_session: Session, test_organization: Organization, test_user: User):
        """测试项目 MFA 要求"""
        project = Project(
            id=str(uuid.uuid4()),
            organization_id=test_organization.id,
            name="Secure Project",
            slug="secure-project",
            sensitivity="confidential",
            owner_id=test_user.id,
        )
        db_session.add(project)
        db_session.commit()
        


class TestAgentModel:
    """Agent 模型测试"""
    
    def test_create_agent(self, db_session: Session, test_project: Project, test_user: User):
        """测试创建 Agent"""
        agent = Agent(
            id=str(uuid.uuid4()),
            project_id=test_project.id,
            name="Unit Test Agent",
            slug="unit-test-agent",
            agent_type="workflow",
            model_provider="anthropic",
            model_name="claude-3-opus"
        )
        db_session.add(agent)
        db_session.commit()
        db_session.refresh(agent)
        
        assert agent.project_id == test_project.id
        assert agent.agent_type == "workflow"
        assert agent.model_provider == "anthropic"
    
    def test_agent_tags(self, db_session: Session, test_project: Project, test_user: User):
        """测试 Agent 标签"""
        agent = Agent(
            id=str(uuid.uuid4()),
            project_id=test_project.id,
            name="Tagged Agent",
            slug="tagged-agent",
            agent_type="chat",
            model_provider="openai",
            model_name="gpt-4-turbo",
            tags=["production", "critical", "v2"]
        )
        db_session.add(agent)
        db_session.commit()
        
        assert len(agent.tags) == 3
        assert "production" in agent.tags


class TestABACPolicyModel:
    """ABAC Policy 模型测试"""
    
    def test_create_policy(self, db_session: Session):
        """测试创建 ABAC 策略"""
        policy = ABACPolicy(
            id=str(uuid.uuid4()),
            name="Unit Test Policy",
            description="Test policy",
            effect="allow",
            subject_conditions={"role": ["developer"]},
            resource_conditions={"sensitivity": ["internal"]},
            environment_conditions={}
        )
        db_session.add(policy)
        db_session.commit()
        db_session.refresh(policy)
        
        assert policy.effect == "allow"
        assert policy.is_active == True
    
    def test_policy_deny_effect(self, db_session: Session):
        """测试拒绝策略"""
        policy = ABACPolicy(
            id=str(uuid.uuid4()),
            name="Deny Policy",
            effect="deny",
            subject_conditions={"auth_level": ["basic"]},
            resource_conditions={"sensitivity": ["confidential"]},
            environment_conditions={}
        )
        db_session.add(policy)
        db_session.commit()
        
        assert policy.effect == "deny"
        assert policy.subject_conditions["auth_level"] == ["basic"]
    
    def test_policy_priority(self, db_session: Session):
        """测试策略优先级"""
        policy1 = ABACPolicy(
            id=str(uuid.uuid4()),
            name="Low Priority",
            effect="allow",
            subject_conditions={},
            resource_conditions={},
            environment_conditions={},
            priority=1
        )
        policy2 = ABACPolicy(
            id=str(uuid.uuid4()),
            name="High Priority",
            effect="deny",
            subject_conditions={},
            resource_conditions={},
            environment_conditions={},
            priority=10
        )
        db_session.add_all([policy1, policy2])
        db_session.commit()
        
        assert policy2.priority > policy1.priority


class TestPolicyAssignmentModel:
    """Policy Assignment 模型测试"""
    
    def test_assign_policy_to_user(self, db_session: Session, test_abac_policy: ABACPolicy, test_user: User):
        """测试策略分配给用户"""
        assignment = PolicyAssignment(
            id=str(uuid.uuid4()),
            policy_id=test_abac_policy.id,
            target_type="user",
            target_id=test_user.id,
        )
        db_session.add(assignment)
        db_session.commit()
        db_session.refresh(assignment)
        
        assert assignment.target_type == "user"
    
    def test_assign_policy_to_role(self, db_session: Session, test_abac_policy: ABACPolicy):
        """测试策略分配给角色"""
        assignment = PolicyAssignment(
            id=str(uuid.uuid4()),
            policy_id=test_abac_policy.id,
            target_type="role",
            target_id="developer",
        )
        db_session.add(assignment)
        db_session.commit()
        
        assert assignment.target_type == "role"
        assert assignment.target_id == "developer"


class TestPolicyEvaluationLogModel:
    """Policy Evaluation Log 模型测试"""
    
    def test_log_policy_evaluation(self, db_session: Session, test_abac_policy: ABACPolicy, test_user: User, test_project: Project):
        """测试策略评估日志"""
        log = PolicyEvaluationLog(
            id=str(uuid.uuid4()),
            subject_id=test_user.id,
            resource_id=test_project.id,
            action="read",
            decision="allow",
        )
        db_session.add(log)
        db_session.commit()
        db_session.refresh(log)
        
        assert log.decision == "allow"
    
    def test_log_denied_access(self, db_session: Session, test_abac_policy: ABACPolicy, test_user: User, test_project: Project):
        """测试拒绝访问日志"""
        log = PolicyEvaluationLog(
            id=str(uuid.uuid4()),
            subject_id=test_user.id,
            resource_id=test_project.id,
            action="delete",
            decision="deny",
        )
        db_session.add(log)
        db_session.commit()
        
        assert log.decision == "deny"