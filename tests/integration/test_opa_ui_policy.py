import os
import pytest
import httpx

pytestmark = pytest.mark.integration

OPA_URL = os.getenv("OPA_URL", "http://127.0.0.1:8181")
OPA_PATH = os.getenv("OPA_UI_POLICY_PATH", "/v1/data/ui/allow")

def _post(input_doc: dict) -> dict:
    url = OPA_URL.rstrip("/") + OPA_PATH
    r = httpx.post(url, json={"input": input_doc}, timeout=3.0)
    r.raise_for_status()
    return r.json()

def _is_allowed(result):
    """Handle both boolean and set/array results from OPA"""
    if isinstance(result, bool):
        return result
    if isinstance(result, list):
        return True in result
    if isinstance(result, (set, tuple)):
        return True in result
    return False

def test_opa_ui_allow_user_chat():
    """用户应该可以访问聊天功能"""
    data = _post({"resource": {"type": "menu", "id": "chat"}, "subject": {"is_admin": False}})
    assert _is_allowed(data.get("result")), f"Expected allow, got: {data}"

def test_opa_ui_deny_user_admin():
    """用户不应该访问管理功能"""
    data = _post({"resource": {"type": "menu", "id": "admin"}, "subject": {"is_admin": False}})
    assert not _is_allowed(data.get("result")), f"Expected deny, got: {data}"

def test_opa_ui_allow_admin_admin():
    """管理员应该可以访问管理功能"""
    data = _post({"resource": {"type": "menu", "id": "admin"}, "subject": {"is_admin": True}})
    assert _is_allowed(data.get("result")), f"Expected allow, got: {data}"
