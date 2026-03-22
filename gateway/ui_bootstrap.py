from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

import httpx
import os
import yaml

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
    timeout_s: float = 3.0,
) -> bool:
    """
    Phase-17 UI bootstrap ABAC contract.

    Current OPA-side tests expect:
      - input.subject.is_admin
      - input.resource.type == "menu"

    To keep the gateway/UI layer aligned with the existing OPA policy contract,
    we send the canonical fields expected by policy/tests:
      - subject
      - tenant
      - resource.type
      - action

    We also preserve user/kind fields in the same payload so downstream policy
    evolution can remain forward-compatible during refactors, but the primary
    contract is subject/type.
    """
    resource_id = resource.get("id")
    resource_kind = resource.get("kind") or resource.get("type") or "menu"

    payload = {
        "input": {
            # canonical contract used by current OPA tests/policies
            "subject": user or {},
            "tenant": tenant or {},
            "resource": {
                **(resource or {}),
                "type": resource_kind,
                "kind": resource_kind,
                "id": resource_id,
            },
            "action": action,
            # preserved aliases for gateway-side callers that still think in user/*
            "user": user or {},
        }
    }

    async with httpx.AsyncClient(timeout=timeout_s) as client:
        r = await client.post(f"{OPA_URL}{OPA_POLICY_PATH}", json=payload)
        r.raise_for_status()
        data = r.json()

    result = data.get("result", False)
    if isinstance(result, bool):
        return result
    if isinstance(result, list):
        return True in result
    if isinstance(result, (set, tuple)):
        return True in result
    return False


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
            resource={"type": "menu", "id": rid},
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