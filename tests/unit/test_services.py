"""
认证服务层单元测试
测试 auth_service.py 中的核心函数
"""
import pytest
from uuid import uuid4
from datetime import datetime, timedelta

from services.auth_service import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_token
)
from config.settings import settings


class TestPasswordHashing:
    """密码哈希测试"""
    
    def test_hash_password_returns_string(self):
        """测试哈希密码返回字符串"""
        result = hash_password("testpassword123")
        assert isinstance(result, str)
        assert len(result) > 0
    
    def test_hash_password_different_hashes(self):
        """测试相同密码生成不同哈希"""
        hash1 = hash_password("samepassword")
        hash2 = hash_password("samepassword")
        assert hash1 != hash2  # bcrypt 使用随机盐
    
    def test_verify_password_correct(self):
        """测试验证正确密码"""
        password = "testpassword123"
        hashed = hash_password(password)
        assert verify_password(password, hashed) is True
    
    def test_verify_password_incorrect(self):
        """测试验证错误密码"""
        password = "testpassword123"
        hashed = hash_password(password)
        assert verify_password("wrongpassword", hashed) is False
    
    def test_verify_password_empty(self):
        """测试空密码验证"""
        assert verify_password("", "somehash") is False


class TestAccessToken:
    """访问令牌测试"""
    
    def test_create_access_token_returns_string(self):
        """测试创建访问令牌返回字符串"""
        token = create_access_token(
            subject="test@example.com",
            user_id=uuid4(),
            role="user"
        )
        assert isinstance(token, str)
        assert len(token) > 0
    
    def test_create_access_token_contains_user_id(self):
        """测试令牌包含用户 ID"""
        user_id = uuid4()
        token = create_access_token(
            subject="test@example.com",
            user_id=user_id,
            role="user"
        )
        payload = decode_token(token)
        assert payload is not None
        assert payload["user_id"] == str(user_id)
    
    def test_create_access_token_contains_role(self):
        """测试令牌包含角色"""
        token = create_access_token(
            subject="test@example.com",
            user_id=uuid4(),
            role="admin"
        )
        payload = decode_token(token)
        assert payload["role"] == "admin"
    
    def test_create_access_token_with_org_id(self):
        """测试令牌包含组织 ID"""
        org_id = uuid4()
        token = create_access_token(
            subject="test@example.com",
            user_id=uuid4(),
            role="user",
            organization_id=org_id
        )
        payload = decode_token(token)
        assert payload["organization_id"] == str(org_id)
    
    def test_create_access_token_custom_expiry(self):
        """测试自定义过期时间"""
        token = create_access_token(
            subject="test@example.com",
            user_id=uuid4(),
            role="user",
            expires_delta=timedelta(minutes=5)
        )
        payload = decode_token(token)
        assert payload["exp"] is not None


class TestRefreshToken:
    """刷新令牌测试"""
    
    def test_create_refresh_token_returns_string(self):
        """测试创建刷新令牌返回字符串"""
        token = create_refresh_token(
            subject="test@example.com",
            user_id=uuid4()
        )
        assert isinstance(token, str)
    
    def test_create_refresh_token_type(self):
        """测试刷新令牌类型正确"""
        token = create_refresh_token(
            subject="test@example.com",
            user_id=uuid4()
        )
        payload = decode_token(token)
        assert payload["type"] == "refresh"


class TestTokenVerification:
    """令牌验证测试"""
    
    def test_verify_valid_access_token(self):
        """测试验证有效的访问令牌"""
        token = create_access_token(
            subject="test@example.com",
            user_id=uuid4(),
            role="user"
        )
        payload = verify_token(token, token_type="access")
        assert payload is not None
        assert payload["sub"] == "test@example.com"
    
    def test_verify_invalid_token(self):
        """测试验证无效令牌"""
        payload = verify_token("invalid_token", token_type="access")
        assert payload is None
    
    def test_verify_wrong_token_type(self):
        """测试验证错误的令牌类型"""
        access_token = create_access_token(
            subject="test@example.com",
            user_id=uuid4(),
            role="user"
        )
        # 用 refresh 类型验证 access 令牌
        payload = verify_token(access_token, token_type="refresh")
        assert payload is None
    
    def test_verify_expired_token(self):
        """测试验证过期令牌"""
        token = create_access_token(
            subject="test@example.com",
            user_id=uuid4(),
            role="user",
            expires_delta=timedelta(seconds=-1)  # 已过期
        )
        payload = verify_token(token, token_type="access")
        assert payload is None