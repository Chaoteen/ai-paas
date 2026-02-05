from __future__ import annotations

import re
import sys
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, Tuple, List

REPO_ROOT = Path(__file__).resolve().parents[1]

STAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
BACKUP_DIR = REPO_ROOT / ".patch_backups" / STAMP
BACKUP_DIR.mkdir(parents=True, exist_ok=True)


def log(msg: str) -> None:
    print(f"[patch] {msg}")


def backup_file(p: Path) -> None:
    if not p.exists():
        return
    rel = p.relative_to(REPO_ROOT)
    dst = BACKUP_DIR / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(p.read_text(encoding="utf-8"), encoding="utf-8")


def write_file(p: Path, content: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    if p.exists():
        backup_file(p)
    p.write_text(content, encoding="utf-8")


def read_text(p: Path) -> Optional[str]:
    if not p.exists():
        return None
    return p.read_text(encoding="utf-8")


def find_first_existing(paths: List[Path]) -> Optional[Path]:
    for p in paths:
        if p.exists():
            return p
    return None


def insert_after_pattern(text: str, pattern: str, insert: str, *, flags=re.MULTILINE) -> Tuple[str, bool]:
    m = re.search(pattern, text, flags)
    if not m:
        return text, False
    idx = m.end()
    return text[:idx] + insert + text[idx:], True


def ensure_line_exists(text: str, line: str) -> Tuple[str, bool]:
    if line in text:
        return text, False
    return text + ("" if text.endswith("\n") else "\n") + line + "\n", True


def yaml_has_menu_id(yaml_text: str, menu_id: str) -> bool:
    # naive but robust enough: id: xxx
    return re.search(rf"(?m)^\s*-\s*id:\s*{re.escape(menu_id)}\s*$", yaml_text) is not None or \
           re.search(rf"(?m)^\s*id:\s*{re.escape(menu_id)}\s*$", yaml_text) is not None


def upsert_menus_yaml(p: Path) -> None:
    content = read_text(p)
    if content is None:
        log(f"menus.yaml not found, creating: {p}")
        content = "menus:\n"
    else:
        backup_file(p)

    if "menus:" not in content:
        # Wrap existing content
        content = "menus:\n" + "\n".join([f"  # migrated: {line}" for line in content.splitlines()]) + "\n"

    additions = []
    def add_menu_block(menu_id: str, title: str, route: str, iframe_url: str, category: str):
        if yaml_has_menu_id(content, menu_id):
            return
        additions.append(
f"""  - id: {menu_id}
    title: {title}
    type: iframe
    route: {route}
    iframe_url: {iframe_url}
    category: {category}
"""
        )

    # 你现状：flowise/opa 已有；这里保证 promptflow/langgraph 存在
    add_menu_block("promptflow", "PromptFlow", "/plugins/promptflow", "/external/promptflow/", "tools")
    add_menu_block("langgraph", "LangGraph", "/plugins/langgraph", "/external/langgraph/", "tools")

    if additions:
        # append at end
        content = content.rstrip() + "\n\n" + "\n".join(additions) + "\n"
        p.write_text(content, encoding="utf-8")
        log(f"menus.yaml updated (+{len(additions)} menus): {p}")
    else:
        log(f"menus.yaml already contains promptflow/langgraph: {p}")


def write_ui_bootstrap_py(p: Path) -> None:
    content = f'''from __future__ import annotations

from typing import Any, Dict, List, Optional
from pathlib import Path
import os
import yaml
import httpx

# ---------------------------------------------------------------------
# UI Bootstrap Builder
#   - Load menus from YAML
#   - Ask OPA per menu: allow?
#   - Return {{user, tenant, menus, capabilities, layout}}
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
        data = yaml.safe_load(f) or {{}}
    return data.get("menus", []) or []


async def opa_allow(
    *,
    user: Dict[str, Any],
    tenant: Dict[str, Any],
    resource: Dict[str, Any],
    action: str = "view",
    timeout_s: float = 3.0
) -> bool:
    payload = {{
        "input": {{
            "user": user or {{}},
            "tenant": tenant or {{}},
            "resource": resource or {{}},
            "action": action,
        }}
    }}
    async with httpx.AsyncClient(timeout=timeout_s) as client:
        r = await client.post(f"{{OPA_URL}}{{OPA_POLICY_PATH}}", json=payload)
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
            resource={{"kind": "menu", "id": rid}},
            action="view",
        )
        if ok:
            allowed.append(m)

    return {{
        "user": user_ctx or {{}},
        "tenant": tenant_ctx or {{}},
        "menus": allowed,
        "capabilities": {{}},
        "layout": {{}},
    }}
'''
    write_file(p, content)
    log(f"created/updated: {p}")


def upsert_rego_policy(p: Path) -> None:
    # 写成“覆盖式最小可用”版本：你可以再按你现有策略改细
    # 这里的设计是：admin 放行；非 admin 允许 flowise/promptflow/langgraph；opa console 你可自行加
    content = '''package ui

default allow = false

# Admin: full access
allow {
  input.user.is_admin == true
}

# Menus allowed for non-admin (minimal)
allow {
  input.resource.kind == "menu"
  input.action == "view"
  input.resource.id in {"flowise", "promptflow", "langgraph", "opa"}
}
'''
    # 如果文件存在且不是我们的结构，则只做“补丁提醒”，避免误伤你已有复杂策略
    existing = read_text(p)
    if existing is None:
        write_file(p, content)
        log(f"created: {p}")
        return

    # 如果已经有 package ui 并且包含 allow，就不覆盖，只提示你手工合并
    if "package ui" in existing and "allow" in existing:
        log(f"OPA policy exists, NOT overwriting: {p}")
        log("  -> Please ensure it allows menu ids: flowise, promptflow, langgraph (and opa if needed).")
        return

    # 否则覆盖
    write_file(p, content)
    log(f"updated: {p}")


def patch_plugin_tsx(p: Path) -> None:
    # 将 Plugin.tsx 变成通用容器：通过 /plugins/:pluginId 读取 bootstrap.menus 的 iframe_url
    content = '''import React, { useEffect, useMemo, useRef } from "react";
import { useLocation, useParams } from "react-router-dom";

/**
 * Assumption:
 *   You already call GET /api/ui/bootstrap somewhere and store it in a global state.
 *
 * Replace `useBootstrap()` with your actual bootstrap store hook.
 * Minimal expected shape:
 *   {
 *     token: string,
 *     user: any,
 *     tenant: any,
 *     menus: Array<{ id, title, type, iframe_url }>
 *   }
 */
function useBootstrap(): any {
  // TODO: wire this to your existing state/store
  // This placeholder prevents TS compile errors if you paste directly.
  return (window as any).__AIOS_BOOTSTRAP__ || { token: "", user: {}, tenant: {}, menus: [] };
}

type HostMessage =
  | { type: "AIOS_HOST_CONTEXT"; payload: any }
  | { type: "AIOS_HOST_PING"; ts: number };

type PluginMessage =
  | { type: "AIOS_PLUGIN_READY"; pluginId?: string }
  | { type: "AIOS_PLUGIN_RESIZE"; height: number }
  | { type: "AIOS_PLUGIN_NAVIGATE"; path: string };

export const PluginPage: React.FC = () => {
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const { pluginId } = useParams();
  const loc = useLocation();
  const bs = useBootstrap();

  const plugin = useMemo(() => {
    return (bs.menus || []).find((m: any) => m.id === pluginId);
  }, [bs.menus, pluginId]);

  function postContext() {
    const iframe = iframeRef.current;
    if (!iframe?.contentWindow) return;

    const payload = {
      v: 1,
      token: bs.token,
      user: bs.user,
      tenant: bs.tenant,
      gatewayBase: "/api",
      pluginId,
      hostPath: loc.pathname + loc.search,
    };

    const msg: HostMessage = { type: "AIOS_HOST_CONTEXT", payload };
    iframe.contentWindow.postMessage(msg, "*");
  }

  useEffect(() => {
    function onMessage(ev: MessageEvent) {
      const msg = ev.data as PluginMessage;
      if (!msg || typeof msg !== "object") return;

      if (msg.type === "AIOS_PLUGIN_READY") {
        postContext();
      }

      if (msg.type === "AIOS_PLUGIN_RESIZE") {
        const h = Math.max(300, Math.min(msg.height, 5000));
        if (iframeRef.current) iframeRef.current.style.height = `${h}px`;
      }
    }

    window.addEventListener("message", onMessage);
    return () => window.removeEventListener("message", onMessage);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pluginId, bs.token]);

  if (!pluginId) return <div style={{ padding: 16 }}>Missing pluginId</div>;
  if (!plugin) return <div style={{ padding: 16 }}>Plugin not found: {pluginId}</div>;
  if (plugin.type !== "iframe") return <div style={{ padding: 16 }}>Not an iframe plugin: {pluginId}</div>;

  return (
    <div style={{ height: "100%", width: "100%" }}>
      <iframe
        ref={iframeRef}
        title={plugin.title || pluginId}
        src={plugin.iframe_url}
        style={{ width: "100%", height: "80vh", border: "none" }}
        onLoad={() => setTimeout(postContext, 200)}
      />
    </div>
  );
};
'''
    write_file(p, content)
    log(f"created/updated: {p}")
    log("NOTE: Replace useBootstrap() placeholder with your real bootstrap store/hook.")


def patch_router_tsx(p: Path) -> None:
    text = read_text(p)
    if text is None:
        log(f"Router.tsx not found, skipping: {p}")
        return
    backup_file(p)

    # 1) ensure import
    if "PluginPage" not in text:
        # Try to insert near other imports
        insert_stmt = '\nimport { PluginPage } from "../pages/Plugin";\n'
        # common patterns: import { OpaConsole } ...
        text2, ok = insert_after_pattern(text, r'(?m)^import .*?;\s*$', insert_stmt)
        if not ok:
            # fallback: prepend after first import line
            lines = text.splitlines(True)
            if lines:
                lines.insert(1, insert_stmt)
                text2 = "".join(lines)
            else:
                text2 = insert_stmt + text
        text = text2

    # 2) ensure route exists
    if re.search(r'path\s*=\s*"/plugins/:pluginId"', text) or "/plugins/:pluginId" in text:
        log("Router already has /plugins/:pluginId route.")
    else:
        # try insert into <Routes> ... </Routes>
        route_line = '      <Route path="/plugins/:pluginId" element={<PluginPage />} />\n'
        # Find a good insertion point: after other <Route ... />
        m = re.search(r'(?s)<Routes[^>]*>.*?</Routes>', text)
        if m:
            block = m.group(0)
            # insert before </Routes>
            block2 = re.sub(r'</Routes>', route_line + '    </Routes>', block, count=1)
            text = text.replace(block, block2)
            log("Inserted /plugins/:pluginId route into <Routes>.")
        else:
            log("Could not locate <Routes> block; please add this route manually:")
            log(route_line.strip())

    p.write_text(text, encoding="utf-8")
    log(f"updated: {p}")


def patch_vite_proxy(vite_path: Path) -> None:
    text = read_text(vite_path)
    if text is None:
        log(f"vite config not found: {vite_path}")
        return
    backup_file(vite_path)

    # If already has /external/promptflow or /external/langgraph, skip
    if "/external/promptflow" in text and "/external/langgraph" in text:
        log(f"vite proxy already contains promptflow/langgraph: {vite_path}")
        return

    # Try to find proxy: { ... }
    # We insert blocks inside proxy object.
    proxy_match = re.search(r'proxy\s*:\s*\{', text)
    if not proxy_match:
        log(f"Could not find proxy object in vite config: {vite_path}")
        log("Please add proxy entries manually for /external/promptflow and /external/langgraph.")
        return

    insertion = """
    "/external/promptflow": {
      target: "http://127.0.0.1:8080",
      changeOrigin: true,
      rewrite: (path) => path.replace(/^\\/external\\/promptflow/, ""),
    },
    "/external/langgraph": {
      target: "http://127.0.0.1:8123",
      changeOrigin: true,
      rewrite: (path) => path.replace(/^\\/external\\/langgraph/, ""),
    },
"""
    # Insert after proxy:{ line
    idx = proxy_match.end()
    text = text[:idx] + insertion + text[idx:]

    vite_path.write_text(text, encoding="utf-8")
    log(f"updated: {vite_path}")
    log("NOTE: Adjust target ports (8080/8123) to your actual PromptFlow/LangGraph services.")


def locate_gateway_entry_file() -> Optional[Path]:
    # Common candidates
    candidates = [
        REPO_ROOT / "gateway" / "main.py",
        REPO_ROOT / "gateway" / "app.py",
        REPO_ROOT / "gateway" / "server.py",
    ]
    p = find_first_existing(candidates)
    if p:
        return p

    # fallback: search for FastAPI()
    for p in (REPO_ROOT / "gateway").rglob("*.py"):
        t = read_text(p)
        if not t:
            continue
        if "FastAPI(" in t and "/api/ui/bootstrap" in t:
            return p
        if "FastAPI(" in t and ("include_router" in t or "app =" in t):
            return p
    return None


def patch_gateway_entry_for_bootstrap(entry: Path) -> None:
    text = read_text(entry)
    if text is None:
        return
    if "/api/ui/bootstrap" in text:
        log(f"Gateway entry already has /api/ui/bootstrap: {entry}")
        return

    backup_file(entry)

    # Ensure imports
    if "build_bootstrap" not in text:
        # add import line
        imp = "from gateway.ui_bootstrap import build_bootstrap\n"
        # Insert after existing imports
        text2, ok = insert_after_pattern(text, r'(?m)^(from|import)\s+.*$', "\n" + imp)
        if not ok:
            text = imp + "\n" + text
        else:
            text = text2

    # Add endpoint skeleton with TODO depends
    endpoint = """
# ---------------------------------------------------------------------
# UI Bootstrap endpoint (added by patch)
# NOTE: Replace get_user_ctx/get_tenant_ctx with your existing Depends hooks.
# ---------------------------------------------------------------------
try:
    from fastapi import Depends
except Exception:
    Depends = None  # type: ignore

def get_user_ctx():
    # TODO: wire to your existing JWT claims extraction
    # should return dict like: {user_id, tenant_id, is_admin, display_name, ...}
    return {"user_id": "dev", "tenant_id": "dev", "is_admin": True, "display_name": "dev"}

def get_tenant_ctx():
    # TODO: wire to your tenant resolver
    return {"tenant_id": "dev"}

"""
    if "def get_user_ctx" not in text:
        # place near app = FastAPI()
        text2, ok = insert_after_pattern(text, r'(?m)^app\s*=\s*FastAPI\([^)]*\)\s*', endpoint)
        if not ok:
            # fallback append
            text = text.rstrip() + "\n\n" + endpoint + "\n"
        else:
            text = text2

    route = """
@app.get("/api/ui/bootstrap")
async def ui_bootstrap(user_ctx=Depends(get_user_ctx), tenant_ctx=Depends(get_tenant_ctx)):
    return await build_bootstrap(user_ctx, tenant_ctx)
"""
    if "/api/ui/bootstrap" not in text:
        # try insert after app = FastAPI(...)
        text2, ok = insert_after_pattern(text, r'(?m)^app\s*=\s*FastAPI\([^)]*\)\s*', route)
        if not ok:
            text = text.rstrip() + "\n\n" + route + "\n"
        else:
            text = text2

    entry.write_text(text, encoding="utf-8")
    log(f"patched gateway entry with /api/ui/bootstrap skeleton: {entry}")
    log("IMPORTANT: Replace get_user_ctx/get_tenant_ctx with your real JWT/tenant Depends.")


def main() -> None:
    log(f"repo root: {REPO_ROOT}")
    log(f"backups: {BACKUP_DIR}")

    # 1) gateway ui_bootstrap.py
    write_ui_bootstrap_py(REPO_ROOT / "gateway" / "ui_bootstrap.py")

    # 2) menus.yaml
    menus_yaml = REPO_ROOT / "gateway" / "ui_def" / "menus.yaml"
    upsert_menus_yaml(menus_yaml)

    # 3) opa policy
    rego = REPO_ROOT / "ops" / "opa" / "policy" / "ui.rego"
    upsert_rego_policy(rego)

    # 4) webapp Plugin.tsx
    plugin_tsx = REPO_ROOT / "webapp" / "src" / "pages" / "Plugin.tsx"
    patch_plugin_tsx(plugin_tsx)

    # 5) webapp Router.tsx
    router_tsx = REPO_ROOT / "webapp" / "src" / "app" / "Router.tsx"
    patch_router_tsx(router_tsx)

    # 6) vite proxy
    vite_cfg = find_first_existing([
        REPO_ROOT / "webapp" / "vite.config.ts",
        REPO_ROOT / "webapp" / "vite.config.js",
        REPO_ROOT / "webapp" / "vite.config.mjs",
    ])
    if vite_cfg:
        patch_vite_proxy(vite_cfg)
    else:
        log("vite config not found under webapp/, skipping proxy patch.")

    # 7) patch gateway entry
    entry = locate_gateway_entry_file()
    if entry:
        patch_gateway_entry_for_bootstrap(entry)
    else:
        log("Could not locate gateway entry file. Please add bootstrap endpoint manually.")
        log("Add this to your FastAPI entry:")
        print("""
from fastapi import Depends
from gateway.ui_bootstrap import build_bootstrap

@app.get("/api/ui/bootstrap")
async def ui_bootstrap(user_ctx=Depends(<your_user_dep>), tenant_ctx=Depends(<your_tenant_dep>)):
    return await build_bootstrap(user_ctx, tenant_ctx)
""".strip())

    log("DONE.")
    log("Next steps:")
    log("  1) Ensure PromptFlow/LangGraph services are running on the ports you set in vite proxy.")
    log("  2) Ensure /api/ui/bootstrap uses real JWT claims and tenant ctx (replace skeleton deps).")
    log("  3) Frontend: wire useBootstrap() to your real bootstrap store/hook (remove placeholder).")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log("ERROR: " + repr(e))
        sys.exit(1)
