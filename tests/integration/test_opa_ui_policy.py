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

def test_opa_ui_allow_user_chat():
    data = _post({"resource": {"type": "menu", "id": "chat"}, "subject": {"is_admin": False}})
    assert data.get("result") is True, data

def test_opa_ui_deny_user_admin():
    data = _post({"resource": {"type": "menu", "id": "admin"}, "subject": {"is_admin": False}})
    assert data.get("result") is False, data

def test_opa_ui_allow_admin_admin():
    data = _post({"resource": {"type": "menu", "id": "admin"}, "subject": {"is_admin": True}})
    assert data.get("result") is True, data
