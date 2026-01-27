#!/usr/bin/env python3
from __future__ import annotations

import os
import json
import time
from typing import Any, Dict, List

import httpx
import jwt

BASE_URL = os.getenv("AI_PAAS_BASE_URL", "http://127.0.0.1:8000")
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
            if m.get("children"):
                rec(m["children"])
    rec(menus or [])
    return out

def fetch(token: str) -> Dict[str, Any]:
    url = BASE_URL.rstrip("/") + "/api/ui/bootstrap"
    r = httpx.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=5.0)
    r.raise_for_status()
    return r.json()

def main() -> int:
    print("BASE_URL  :", BASE_URL)
    print("JWT_ALG   :", JWT_ALG)
    print("JWT_SECRET:", JWT_SECRET)
    print("")

    t_user = mk_token("user_a", "tenant_a", False)
    t_admin = mk_token("admin_a", "tenant_a", True)

    print("== TOKENS (first 32 chars) ==")
    print("user :", str(t_user)[:32] + "...")
    print("admin:", str(t_admin)[:32] + "...")
    print("")

    u = fetch(t_user)
    a = fetch(t_admin)

    u_ids = flatten_menu_ids(u.get("menus", []))
    a_ids = flatten_menu_ids(a.get("menus", []))

    print("== USER menus ==")
    print(json.dumps(u_ids, ensure_ascii=False, indent=2))
    print("")
    print("== ADMIN menus ==")
    print(json.dumps(a_ids, ensure_ascii=False, indent=2))
    print("")

    # key assertions (printed, not raising)
    must_hide = {"admin", "promptflow", "langgraph"}
    print("== EXPECTATIONS ==")
    print("user should NOT have:", sorted(must_hide))
    print("admin should have   :", sorted(must_hide))
    print("")
    print("user_has_forbidden :", sorted(must_hide.intersection(set(u_ids))))
    print("admin_missing      :", sorted(must_hide.difference(set(a_ids))))

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
