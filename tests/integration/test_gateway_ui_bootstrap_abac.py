import os
import time
import json
from typing import Any, Dict, List

import pytest
import httpx
import jwt

pytestmark = pytest.mark.integration

BASE_URL = os.getenv("AI_PAAS_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
JWT_SECRET = os.getenv("JWT_SECRET", "CHANGE_ME")
JWT_ALG = os.getenv("JWT_ALG", "HS256")

def mk_token(user_id: str, tenant_id: str, is_admin: bool) -> str:
    now = int(time.time())
    payload = {
        "user_id": user_id,
        "tenant_id": tenant_id,
        "is_admin": is_admin,
        "display_name": user_id,
        "iat": now,
        "exp": now + 3600,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)

def flatten_menu_ids(menus: List[Dict[str, Any]]) -> List[str]:
    out: List[str] = []
    def rec(ms):
        for m in ms:
            mid = m.get("id")
            if mid:
                out.append(mid)
            children = m.get("children") or []
            if children:
                rec(children)
    rec(menus or [])
    return out

def fetch_bootstrap(token: str) -> Dict[str, Any]:
    r = httpx.get(
        f"{BASE_URL}/api/ui/bootstrap",
        headers={"Authorization": f"Bearer {token}"},
        timeout=5.0,
    )
    r.raise_for_status()
    return r.json()

def test_gateway_ui_bootstrap_abac_user_vs_admin():
    t_user = mk_token("user_a", "tenant_a", False)
    t_admin = mk_token("admin_a", "tenant_a", True)

    user = fetch_bootstrap(t_user)
    admin = fetch_bootstrap(t_admin)

    u_ids = set(flatten_menu_ids(user.get("menus", [])))
    a_ids = set(flatten_menu_ids(admin.get("menus", [])))

    forbidden_for_user = {"admin", "workflows", "promptflow", "langgraph"}
    required_for_admin = {"admin", "workflows", "promptflow", "langgraph"}

    assert forbidden_for_user.isdisjoint(u_ids), f"user menus leaked: {sorted(forbidden_for_user & u_ids)}; all={sorted(u_ids)}"
    missing = required_for_admin - a_ids
    assert not missing, f"admin missing: {sorted(missing)}; all={sorted(a_ids)}"
