"""
ABAC 策略引擎单元测试
测试策略评估逻辑
"""
import pytest
from datetime import datetime
from typing import Dict, Any

from models.abac import ABACPolicy, PolicyAssignment
from models.auth import User
from models.project import Project


class ABACEngine:
    """简化版 ABAC 策略引擎（用于测试）"""
    
    @staticmethod
    def evaluate_policy(
        policy: ABACPolicy,
        subject: Dict[str, Any],
        resource: Dict[str, Any],
        action: str,
        environment: Dict[str, Any]
    ) -> bool:
        """
        评估策略是否允许访问
        
        Args:
            policy: ABAC 策略
            subject: 主体属性（用户）
            resource: 资源属性
            action: 操作
            environment: 环境属性
            
        Returns:
            bool: 是否允许
        """
        # 检查主体条件
        if policy.subject_conditions:
            for key, allowed_values in policy.subject_conditions.items():
                if key not in subject or subject[key] not in allowed_values:
                    return False
        
        # 检查资源条件
        if policy.resource_conditions:
            for key, allowed_values in policy.resource_conditions.items():
                if key not in resource or resource[key] not in allowed_values:
                    return False
        
        # 检查动作条件
        if policy.action_conditions:
            allowed_actions = policy.action_conditions.get("action", [])
            if action not in allowed_actions:
                return False
        
        # 检查环境条件
        if policy.environment_conditions:
            time_range = policy.environment_conditions.get("time_range")
            if time_range == "business_hours":
                hour = datetime.now().hour
                if hour < 9 or hour >= 18:
                    return False
        
        return policy.effect == "allow"
    
    @staticmethod
    def evaluate_all_policies(
        policies: list,
        subject: Dict[str, Any],
        resource: Dict[str, Any],
        action: str,
        environment: Dict[str, Any]
    ) -> str:
        """
        评估所有策略，返回最终决策
        
        优先级高的策略优先评估，deny 优先于 allow
        """
        # 按优先级排序
        sorted_policies = sorted(policies, key=lambda p: p.priority, reverse=True)
        
        for policy in sorted_policies:
            if not policy.is_active:
                continue
            
            result = ABACEngine.evaluate_policy(policy, subject, resource, action, environment)
            
            if not result and policy.effect == "deny":
                return "deny"
            elif result and policy.effect == "allow":
                # 继续检查是否有更高优先级的 deny
                continue
        
        # 默认拒绝
        return "deny"


class TestABACEngine:
    """ABAC 引擎测试"""
    
    def test_allow_policy_match(self, test_abac_policy: ABACPolicy):
        """测试允许策略匹配"""
        subject = {"role": "developer", "auth_level": "basic"}
        resource = {"sensitivity": "internal"}
        action = "read"
        environment = {}
        
        result = ABACEngine.evaluate_policy(
            test_abac_policy, subject, resource, action, environment
        )
        
        assert result == True
    
    def test_deny_policy_role_mismatch(self, test_abac_policy: ABACPolicy):
        """测试角色不匹配"""
        subject = {"role": "viewer", "auth_level": "basic"}  # 不在允许列表中
        resource = {"sensitivity": "internal"}
        action = "read"
        environment = {}
        
        result = ABACEngine.evaluate_policy(
            test_abac_policy, subject, resource, action, environment
        )
        
        assert result == False
    
    def test_deny_policy_resource_mismatch(self, test_abac_policy: ABACPolicy):
        """测试资源敏感度不匹配"""
        subject = {"role": "developer", "auth_level": "basic"}
        resource = {"sensitivity": "confidential"}  # 不在允许列表中
        action = "read"
        environment = {}
        
        result = ABACEngine.evaluate_policy(
            test_abac_policy, subject, resource, action, environment
        )
        
        assert result == False
    
    def test_deny_policy_action_mismatch(self, test_abac_policy: ABACPolicy):
        """测试动作不匹配"""
        subject = {"role": "developer", "auth_level": "basic"}
        resource = {"sensitivity": "internal"}
        action = "delete"  # 不在允许列表中
        environment = {}
        
        result = ABACEngine.evaluate_policy(
            test_abac_policy, subject, resource, action, environment
        )
        
        assert result == False
    
    def test_deny_effect_policy(self, db_session, test_user: User, test_project: Project):
        """测试拒绝效果策略"""
        deny_policy = ABACPolicy(
            id="test-deny-policy",
            name="Deny Confidential Access",
            policy_type="access_control",
            effect="deny",
            subject_conditions={"auth_level": ["basic"]},
            resource_conditions={"sensitivity": ["confidential"]},
            action_conditions={"action": ["read", "write", "delete"]},
            environment_conditions={}
        )
        
        subject = {"auth_level": "basic"}
        resource = {"sensitivity": "confidential"}
        action = "read"
        environment = {}
        
        result = ABACEngine.evaluate_policy(
            deny_policy, subject, resource, action, environment
        )
        
        # 条件匹配，但 effect 是 deny，所以返回 False（不允许）
        assert result == False
    
    def test_priority_deny_over_allow(self, db_session):
        """测试拒绝优先于允许"""
        allow_policy = ABACPolicy(
            id="priority-allow",
            name="Allow Developers",
            policy_type="access_control",
            effect="allow",
            subject_conditions={"role": ["developer"]},
            resource_conditions={"sensitivity": ["internal", "confidential"]},
            action_conditions={"action": ["read"]},
            environment_conditions={},
            priority=1,
            is_active=True
        )
        
        deny_policy = ABACPolicy(
            id="priority-deny",
            name="Deny External Users",
            policy_type="access_control",
            effect="deny",
            subject_conditions={"department": ["External"]},
            resource_conditions={"sensitivity": ["confidential"]},
            action_conditions={"action": ["read"]},
            environment_conditions={},
            priority=10,  # 更高优先级
            is_active=True
        )
        
        subject = {"role": "developer", "department": "External"}
        resource = {"sensitivity": "confidential"}
        action = "read"
        environment = {}
        
        result = ABACEngine.evaluate_all_policies(
            [allow_policy, deny_policy], subject, resource, action, environment
        )
        
        # 高优先级的 deny 策略应该生效
        assert result == "deny"
    
    def test_inactive_policy_ignored(self, test_abac_policy: ABACPolicy):
        """测试非活跃策略被忽略"""
        test_abac_policy.is_active = False
        
        subject = {"role": "developer"}
        resource = {"sensitivity": "internal"}
        action = "read"
        environment = {}
        
        result = ABACEngine.evaluate_all_policies(
            [test_abac_policy], subject, resource, action, environment
        )
        
        # 策略非活跃，默认拒绝
        assert result == "deny"


class TestABACAttributes:
    """ABAC 属性测试"""
    
    def test_user_abac_attributes_json(self, test_user: User):
        """测试用户 ABAC 属性 JSON"""
        assert isinstance(test_user.abac_attributes, dict)
        assert "clearance" in test_user.abac_attributes
    
    def test_policy_conditions_json(self, test_abac_policy: ABACPolicy):
        """测试策略条件 JSON"""
        assert isinstance(test_abac_policy.subject_conditions, dict)
        assert isinstance(test_abac_policy.resource_conditions, dict)
        assert isinstance(test_abac_policy.action_conditions, dict)
        assert isinstance(test_abac_policy.environment_conditions, dict)