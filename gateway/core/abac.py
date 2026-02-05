from __future__ import annotations
from typing import Any, Dict, List
from pathlib import Path
import yaml

from .config import settings
from .opa_client import OPAClient
from .auth import UserContext


def _load_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def load_ui_definition() -> Dict[str, Any]:
    base = Path(settings.UI_DEF_DIR).resolve()
    menus = _load_yaml(base / "menus.yaml")
    caps = _load_yaml(base / "capabilities.yaml")
    layout = _load_yaml(base / "layout.yaml")
    return {
        "menus": menus.get("menus", []),
        "capabilities": caps.get("capabilities", {}),
        "layout": layout.get("layout", {}),
        "features": layout.get("features", {}),
    }


def _flatten_menus(menus: List[dict]) -> List[dict]:
    out = []
    for m in menus:
        out.append(m)
        children = m.get("children") or []
        out.extend(_flatten_menus(children))
    return out


def _filter_menus_by_allow(menus: List[dict], allow_map: Dict[str, bool]) -> List[dict]:
    result = []
    for m in menus:
        mid = m.get("id", "")
        allowed = allow_map.get(mid, True)  # default allow if missing id
        if not allowed:
            continue

        children = m.get("children") or []
        if children:
            m2 = dict(m)
            m2["children"] = _filter_menus_by_allow(children, allow_map)
            # 如果 children 被裁剪为空，你可以选择隐藏父菜单或保留父菜单
            if not m2["children"] and m2.get("route") is None and m2.get("type") is None:
                continue
            result.append(m2)
        else:
            result.append(m)
    return result


async def build_bootstrap(user: UserContext) -> Dict[str, Any]:
    ui = load_ui_definition()

    # 如果不启用 OPA，直接返回全量（但仍建议保留此开关，便于故障降级）
    if not settings.OPA_ENABLED:
        return {
            "user": {"id": user.user_id, "display_name": user.display_name, "is_admin": user.is_admin},
            "tenant": {"id": user.tenant_id, "name": user.tenant_id},
            **ui,
        }

    opa = OPAClient()
    menus = ui.get("menus", [])
    flat = _flatten_menus(menus)

    allow_map: Dict[str, bool] = {}
    for m in flat:
        menu_id = m.get("id") or ""
        if not menu_id:
            continue

        # input schema：OPA-ready
        input_doc = {
            "subject": {
                "user_id": user.user_id,
                "tenant_id": user.tenant_id,
                "is_admin": user.is_admin,
            },
            "action": "ui:read",
            "resource": {
                "type": "menu",
                "id": menu_id,
                "capability": m.get("capability"),
            },
            "context": {},
        }
        allow_map[menu_id] = await opa.query_allow(input_doc)

    filtered_menus = _filter_menus_by_allow(menus, allow_map)

    return {
        "user": {"id": user.user_id, "display_name": user.display_name, "is_admin": user.is_admin},
        "tenant": {"id": user.tenant_id, "name": user.tenant_id},
        "capabilities": ui.get("capabilities", {}),
        "menus": filtered_menus,
        "layout": ui.get("layout", {}),
        "features": ui.get("features", {}),
    }
