"""
数据库集成测试
测试数据库操作、事务和关系
"""
import uuid
import pytest
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from models.auth import User, Organization
from models.project import Project
from models.agent import Agent
from models.abac import ABACPolicy, PolicyAssignment, PolicyEvaluationLog
from models.audit import AuditLog


class TestDatabaseRelations:
    """数据库关系测试"""
    
    def test_organization_user_relationship(self, db_session: Session, test_user: User, test_organization: Organization):
        """测试组织 - 用户关系"""
        # 验证组织所有者
        org = db_session.get(Organization, test_organization.id)
        assert org.owner_id == test_user.id
        
        # 验证用户可以拥有多个组织
        org2 = Organization(
            id=str(uuid.uuid4()),
            name="Second Org",
            slug="second-org",
            owner_id=test_user.id
        )
        db_session.add(org2)
        db_session.commit()
        
        organizations = db_session.query(Organization).filter_by(owner_id=test_user.id).all()
        assert len(organizations) == 2
    
    def test_project_organization_relationship(self, db_session: Session, test_organization: Organization, test_project: Project):
        """测试项目 - 组织关系"""
        project = db_session.get(Project, test_project.id)
        assert project.organization_id == test_organization.id
        
        # 验证组织可以有多个项目
        project2 = Project(
            id=str(uuid.uuid4()),
            organization_id=test_organization.id,
            name="Second Project",
            slug="second-project"
        )
        db_session.add(project2)
        db_session.commit()
        
        projects = db_session.query(Project).filter_by(organization_id=test_organization.id).all()
        assert len(projects) == 2
    
    def test_agent_project_relationship(self, db_session: Session, test_project: Project, test_agent: Agent):
        """测试 Agent - 项目关系"""
        agent = db_session.get(Agent, test_agent.id)
        assert agent.project_id == test_project.id
        
        # 验证项目可以有多个 Agent
        agent2 = Agent(
            id=str(uuid.uuid4()),
            project_id=test_project.id,
            name="Second Agent",
            slug="second-agent",
            agent_type="workflow",
            model_provider="google",
            model_name="gemini-pro"
        )
        db_session.add(agent2)
        db_session.commit()
        
        agents = db_session.query(Agent).filter_by(project_id=test_project.id).all()
        assert len(agents) == 2


class TestDatabaseQueries:
    """数据库查询测试"""
    
    def test_query_users_by_department(self, db_session: Session, test_user: User):
        """测试按部门查询用户"""
        user2 = User(
            id=str(uuid.uuid4()),
            email="user2@example.com",
            username="user2",
            password_hash="hash",
            department="Engineering",
            level="L4"
        )
        user3 = User(
            id=str(uuid.uuid4()),
            email="user3@example.com",
            username="user3",
            password_hash="hash",
            department="Sales",
            level="L3"
        )
        db_session.add_all([user2, user3])
        db_session.commit()
        
        engineering_users = db_session.query(User).filter_by(department="Engineering").all()
        assert len(engineering_users) == 2
        
        sales_users = db_session.query(User).filter_by(department="Sales").all()
        assert len(sales_users) == 1
    
    def test_query_active_policies(self, db_session: Session, test_abac_policy: ABACPolicy):
        """测试查询活跃策略"""
        inactive_policy = ABACPolicy(
            id=str(uuid.uuid4()),
            name="Inactive Policy",
            effect="deny",
            subject_conditions={},
            resource_conditions={},
            environment_conditions={},
            is_active=False
        )
        db_session.add(inactive_policy)
        db_session.commit()
        
        active_policies = db_session.query(ABACPolicy).filter_by(is_active=True).all()
        assert len(active_policies) == 1
        assert active_policies[0].id == test_abac_policy.id
    
    def test_query_policy_evaluations_by_decision(self, db_session: Session, test_abac_policy: ABACPolicy, test_user: User, test_project: Project):
        """测试按决策结果查询策略评估日志"""
        log1 = PolicyEvaluationLog(
            id=str(uuid.uuid4()),
            subject_id=test_user.id,
            resource_id=test_project.id,
            action="read",
            decision="allow",
        )
        log2 = PolicyEvaluationLog(
            id=str(uuid.uuid4()),
            subject_id=test_user.id,
            resource_id=test_project.id,
            action="delete",
            decision="deny",
        )
        log3 = PolicyEvaluationLog(
            id=str(uuid.uuid4()),
            subject_id=test_user.id,
            resource_id=test_project.id,
            action="write",
            decision="allow",
        )
        db_session.add_all([log1, log2, log3])
        db_session.commit()
        
        allowed_logs = db_session.query(PolicyEvaluationLog).filter_by(decision="allow").all()
        denied_logs = db_session.query(PolicyEvaluationLog).filter_by(decision="deny").all()
        
        assert len(allowed_logs) == 2
        assert len(denied_logs) == 1


class TestDatabaseTransactions:
    """数据库事务测试"""
    
    def test_transaction_rollback(self, db_session: Session):
        """测试事务回滚"""
        initial_count = db_session.query(User).count()
        
        try:
            user = User(
                id=str(uuid.uuid4()),
                email="transaction@example.com",
                username="transactionuser",
                password_hash="hash"
            )
            db_session.add(user)
            db_session.flush()  # 不提交
            
            # 模拟错误
            raise ValueError("Simulated error")
        except ValueError:
            db_session.rollback()
        
        final_count = db_session.query(User).count()
        assert final_count == initial_count
    
    def test_transaction_commit(self, db_session: Session):
        """测试事务提交"""
        initial_count = db_session.query(User).count()
        
        user = User(
            id=str(uuid.uuid4()),
            email="commit@example.com",
            username="commituser",
            password_hash="hash"
        )
        db_session.add(user)
        db_session.commit()
        
        final_count = db_session.query(User).count()
        assert final_count == initial_count + 1


class TestAuditLogging:
    """审计日志测试"""
    
    def test_create_audit_log(self, db_session: Session, test_user: User, test_project: Project):
        """测试创建审计日志"""
        audit_log = AuditLog(
            id=str(uuid.uuid4()),
            actor_id=test_user.id,
            actor_type="user",
            action="project.create",
            resource_type="project",
            resource_id=test_project.id,
            status="success",
        )
        db_session.add(audit_log)
        db_session.commit()
        db_session.refresh(audit_log)
        
        assert audit_log.actor_id == test_user.id
        assert audit_log.action == "project.create"
        assert audit_log.status == "success"
    
    def test_query_audit_logs_by_actor(self, db_session: Session, test_user: User, test_project: Project):
        """测试按执行者查询审计日志"""
        logs = [
            AuditLog(
                id=str(uuid.uuid4()),
                actor_id=test_user.id,
                actor_type="user",
                action=f"project.action{i}",
                resource_type="project",
                resource_id=test_project.id,
                status="success"
            )
            for i in range(1, 4)
        ]
        db_session.add_all(logs)
        db_session.commit()
        
        user_logs = db_session.query(AuditLog).filter_by(actor_id=test_user.id).all()
        assert len(user_logs) == 3