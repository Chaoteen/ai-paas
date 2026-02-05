from __future__ import annotations

from typing import Any, Dict, List, Optional
from pathlib import Path
import os
import yaml
import httpx

# ---------------------------------------------------------------------
# UI Bootstrap Builder
#   - Load menus from YAML
#   - Ask OPA per menu: allow?
#   - Return {user, tenant, menus, capabilities, layout}
#
# Integration:
#   In your FastAPI app:
#     from gateway.ui_bootstrap import build_bootstrap
#     @app.get("/api/ui/bootstrap")
#     async def ui_bootstrap(user_ctx=Depends(...), tenant_ctx=Depends(...)):
#         return await build_bootstrap(user_ctx, tenant_ctx)
# ---------------------------------------------------------------------

DEFAULT_MENUS_YAML = os.getenv("AIOS_MENUS_YAML", "gateway/ui_def/menus.yaml")
OPA_URL = os.getenv("OPA_URL", "http://127.0.0.1:8181")
OPA_POLICY_PATH = os.getenv("OPA_POLICY_PATH", "/v1/data/ui/allow")


def load_menus(path: str = DEFAULT_MENUS_YAML) -> List[Dict[str, Any]]:
    p = Path(path)
    if not p.exists():
        return []
    with p.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("menus", []) or []


async def opa_allow(
    *,
    user: Dict[str, Any],
    tenant: Dict[str, Any],
    resource: Dict[str, Any],
    action: str = "view",
    timeout_s: float = 3.0
) -> bool:
    payload = {
        "input": {
            "user": user or {},
            "tenant": tenant or {},
            "resource": resource or {},
            "action": action,
        }
    }
    async with httpx.AsyncClient(timeout=timeout_s) as client:
        r = await client.post(f"{OPA_URL}{OPA_POLICY_PATH}", json=payload)
        r.raise_for_status()
        data = r.json()
        return bool(data.get("result", False))


async def build_bootstrap(user_ctx: Dict[str, Any], tenant_ctx: Dict[str, Any]) -> Dict[str, Any]:
    menus = load_menus()
    allowed: List[Dict[str, Any]] = []

    for m in menus:
        rid = m.get("id")
        if not rid:
            continue
        ok = await opa_allow(
            user=user_ctx,
            tenant=tenant_ctx,
            resource={"kind": "menu", "id": rid},
            action="view",
        )
        if ok:
            allowed.append(m)

    return {
        "user": user_ctx or {},
        "tenant": tenant_ctx or {},
        "menus": allowed,
        "capabilities": {},
        "layout": {},
    }
