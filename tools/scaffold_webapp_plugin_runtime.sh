#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="/home/boris/work/ai-paas"
WEBAPP="$REPO_ROOT/webapp/src"

cd "$REPO_ROOT"

mkdir -p "$WEBAPP/plugins" "$WEBAPP/pages" "$WEBAPP/styles" "$WEBAPP/components" "$WEBAPP/api"

# -----------------------------
# 1) plugin runtime (postMessage)
# -----------------------------
cat > "$WEBAPP/plugins/runtime.ts" <<'TS'
export type PluginHandshakeV1 = {
  type: "aios.plugin.handshake";
  v: 1;
  plugin_id?: string;
  request_id: string;
};

export type PluginContextV1 = {
  type: "aios.host.context";
  v: 1;
  request_id: string;

  // identity / tenancy
  user: { id: string; display_name?: string; is_admin?: boolean };
  tenant: { id: string };

  // short-lived token for plugin -> gateway calls (or plugin backend)
  token?: string;

  // ui tokens
  theme: { mode: "dark" | "light"; tokens: Record<string, string> };
  locale?: string;

  // tracing
  trace_id: string;
};

export type PluginEventV1 =
  | PluginHandshakeV1
  | PluginContextV1
  | { type: "aios.plugin.telemetry"; v: 1; trace_id: string; level: "info" | "warn" | "error"; message: string; data?: any }
  | { type: "aios.plugin.request"; v: 1; trace_id: string; request_id: string; op: string; payload?: any }
  | { type: "aios.host.response"; v: 1; trace_id: string; request_id: string; ok: boolean; payload?: any; error?: string };

export function randomId(prefix = "r"): string {
  return `${prefix}_${Math.random().toString(16).slice(2)}_${Date.now().toString(16)}`;
}

/**
 * Conservative origin check:
 * - allow same-origin
 * - allow explicit allowedOrigins entries
 */
export function isAllowedOrigin(origin: string, allowedOrigins: string[]): boolean {
  if (!origin) return false;
  const same = origin === window.location.origin;
  if (same) return true;
  return allowedOrigins.includes(origin);
}

/**
 * Wait for iframe plugin handshake, then send context.
 * Returns a disposer that removes event listener.
 */
export function bindPluginHandshake(opts: {
  iframeEl: HTMLIFrameElement;
  pluginId: string;
  allowedOrigins: string[]; // plugin origin allowlist (can include same-origin implicitly)
  buildContext: (requestId: string) => PluginContextV1;
  timeoutMs?: number;
  onLog?: (msg: string) => void;
}): { dispose: () => void; ready: Promise<void> } {
  const { iframeEl, pluginId, allowedOrigins, buildContext, timeoutMs = 5000, onLog } = opts;

  let resolved = false;
  let timer: any = null;

  const ready = new Promise<void>((resolve, reject) => {
    timer = setTimeout(() => {
      if (!resolved) {
        reject(new Error(`Plugin handshake timeout (${timeoutMs}ms): ${pluginId}`));
      }
    }, timeoutMs);

    function onMessage(ev: MessageEvent) {
      const data = ev.data as any;
      if (!data || typeof data !== "object") return;
      if (data.type !== "aios.plugin.handshake" || data.v !== 1) return;

      // origin control
      if (!isAllowedOrigin(ev.origin, allowedOrigins)) {
        onLog?.(`Blocked plugin message from origin=${ev.origin} plugin=${pluginId}`);
        return;
      }

      const hs = data as PluginHandshakeV1;
      const requestId = hs.request_id || randomId("hs");

      // send context to the plugin (back to its origin)
      const ctx = buildContext(requestId);
      iframeEl.contentWindow?.postMessage(ctx, ev.origin);

      resolved = true;
      clearTimeout(timer);
      window.removeEventListener("message", onMessage);
      resolve();
    }

    window.addEventListener("message", onMessage);
  });

  return {
    ready,
    dispose: () => {
      clearTimeout(timer);
      window.removeEventListener("message", () => {});
    },
  };
}
TS

# -----------------------------
# 2) bootstrap API types (extend MenuItem)
# -----------------------------
# If file exists, patch carefully; else create minimal.
if [ -f "$WEBAPP/api/bootstrap.ts" ]; then
  # naive patch: ensure MenuItem has optional iframe fields
  perl -0777 -i -pe '
    s/export type MenuItem = \{\n([^}]+)\n\};/export type MenuItem = {\n$1\n  \/** iframe plugin support *\/\n  type?: "iframe";\n  url?: string;\n};/s
  ' "$WEBAPP/api/bootstrap.ts" || true
else
  cat > "$WEBAPP/api/bootstrap.ts" <<'TS'
export type MenuItem = {
  id: string;
  title: string;
  icon?: string;
  route?: string;

  // iframe plugin support
  type?: "iframe";
  url?: string;

  capability?: string;
  children?: MenuItem[];
};

export type Bootstrap = {
  user?: { id: string; display_name?: string; is_admin?: boolean };
  tenant?: { id: string; name?: string };
  menus: MenuItem[];
  capabilities?: Record<string, any>;
  layout?: Record<string, any>;
  features?: Record<string, any>;
};

export async function fetchBootstrap(): Promise<Bootstrap> {
  const base = (import.meta as any).env?.VITE_API_BASE_URL || "";
  const url = (base ? base.replace(/\/+$/, "") : "") + "/api/ui/bootstrap";

  // TODO: replace with real login/session storage
  const token = localStorage.getItem("AI_PAAS_TOKEN") || "";

  const r = await fetch(url, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!r.ok) throw new Error(`bootstrap failed: ${r.status} ${await r.text()}`);
  return (await r.json()) as Bootstrap;
}
TS
fi

# -----------------------------
# 3) Plugin page (iframe host + handshake)
# -----------------------------
cat > "$WEBAPP/pages/Plugin.tsx" <<'TSX'
import React, { useEffect, useMemo, useRef, useState } from "react";
import { useLocation } from "react-router-dom";
import { bindPluginHandshake, randomId, PluginContextV1 } from "../plugins/runtime";

function getQueryParam(search: string, key: string): string {
  const sp = new URLSearchParams(search);
  return (sp.get(key) || "").trim();
}

/**
 * Security policy (v1):
 * - allow only same-origin relative URLs (starting with "/")
 * - later: allow explicit origin allowlist per-plugin manifest
 */
function isSafePluginUrl(url: string): boolean {
  if (!url) return false;
  if (url.startsWith("/")) return true; // same-origin relative path
  return false;
}

function currentThemeTokens(): Record<string, string> {
  const s = getComputedStyle(document.documentElement);
  const keys = [
    "--bg","--panel","--panel-2","--muted","--text","--border","--border-2",
    "--primary","--primary-2","--danger","--warning","--success"
  ];
  const out: Record<string, string> = {};
  for (const k of keys) out[k] = s.getPropertyValue(k).trim();
  return out;
}

export function PluginPage() {
  const loc = useLocation();
  const iframeRef = useRef<HTMLIFrameElement | null>(null);

  const title = getQueryParam(loc.search, "title") || "Plugin";
  const url = getQueryParam(loc.search, "url");
  const pluginId = getQueryParam(loc.search, "id") || title.toLowerCase().replace(/\s+/g, "-");

  const [status, setStatus] = useState<"idle" | "ready" | "error">("idle");
  const [err, setErr] = useState<string>("");

  const traceId = useMemo(() => randomId("trace"), [loc.key]);

  useEffect(() => {
    setStatus("idle");
    setErr("");

    if (!url) {
      setStatus("error");
      setErr("Missing plugin url. Expected: ?url=/external/xxx");
      return;
    }
    if (!isSafePluginUrl(url)) {
      setStatus("error");
      setErr(`Unsafe plugin url (blocked): ${url}`);
      return;
    }

    const iframeEl = iframeRef.current;
    if (!iframeEl) return;

    const token = localStorage.getItem("AI_PAAS_TOKEN") || "";

    const allowedOrigins = [window.location.origin]; // v1: only same-origin plugins

    const { ready } = bindPluginHandshake({
      iframeEl,
      pluginId,
      allowedOrigins,
      timeoutMs: 6000,
      onLog: (m) => console.warn("[plugin-host]", m),
      buildContext: (requestId): PluginContextV1 => {
        const tenantId = localStorage.getItem("AI_PAAS_TENANT") || "tenant_a";
        const userId = localStorage.getItem("AI_PAAS_USER") || "user";
        const isAdmin = localStorage.getItem("AI_PAAS_IS_ADMIN") === "1";

        return {
          type: "aios.host.context",
          v: 1,
          request_id: requestId,
          user: { id: userId, display_name: userId, is_admin: isAdmin },
          tenant: { id: tenantId },
          token: token || undefined,
          theme: { mode: "dark", tokens: currentThemeTokens() },
          locale: navigator.language || "en-US",
          trace_id: traceId,
        };
      },
    });

    ready
      .then(() => setStatus("ready"))
      .catch((e) => {
        setStatus("error");
        setErr(String(e));
      });
  }, [url, pluginId, traceId]);

  if (!url) {
    return (
      <div className="plugin-host">
        <div className="plugin-host__hint">Missing plugin url. Expected: <code>?url=...</code></div>
      </div>
    );
  }

  return (
    <div className="plugin-host">
      <div className="plugin-host__bar">
        <div className="plugin-host__title">{title}</div>
        <div className="plugin-host__meta">
          <span className={`pill ${status === "ready" ? "pill--ok" : status === "error" ? "pill--bad" : ""}`}>
            {status}
          </span>
          <span className="pill">trace: {traceId.slice(0, 10)}</span>
        </div>
      </div>

      {status === "error" ? (
        <div className="plugin-host__error">{err}</div>
      ) : null}

      <div className="plugin-host__frame">
        <iframe
          ref={iframeRef}
          className="plugin-iframe"
          title={title}
          src={url}
          // conservative default; relax per-plugin later via manifest
          sandbox="allow-scripts allow-forms allow-same-origin"
          referrerPolicy="no-referrer"
        />
      </div>

      <div className="plugin-host__hint">
        Plugin URL: <code>{url}</code> (v1 policy: same-origin relative only)
      </div>
    </div>
  );
}
TSX

# -----------------------------
# 4) Sidebar: route iframe menu to /plugin
# -----------------------------
cat > "$WEBAPP/components/Sidebar.tsx" <<'TSX'
import React, { useMemo } from "react";
import { MenuItem } from "../api/bootstrap";
import { Link, useLocation } from "react-router-dom";

function toPluginRoute(item: MenuItem): string {
  const title = encodeURIComponent(item.title || item.id);
  const url = encodeURIComponent(item.url || "");
  const id = encodeURIComponent(item.id || "");
  return `/plugin?title=${title}&url=${url}&id=${id}`;
}

function isActivePath(locPath: string, target: string): boolean {
  if (!target) return false;
  if (target === "/") return locPath === "/";
  return locPath === target || locPath.startsWith(target + "/");
}

function MenuNode({ item, depth = 0 }: { item: MenuItem; depth?: number }) {
  const loc = useLocation();
  const hasChildren = Boolean(item.children && item.children.length > 0);

  const target = useMemo(() => {
    if (item.type === "iframe") return toPluginRoute(item);
    if (item.route) return item.route;
    // non-leaf without route -> no navigation
    return "";
  }, [item]);

  const active =
    (item.route && isActivePath(loc.pathname, item.route)) ||
    (item.type === "iframe" && loc.pathname === "/plugin" && new URLSearchParams(loc.search).get("id") === item.id);

  return (
    <div className={`nav__node ${active ? "nav__node--active" : ""}`} style={{ paddingLeft: 10 + depth * 10 }}>
      {hasChildren ? (
        <>
          <div className="nav__group">{item.title}</div>
          <div className="nav__children">
            {item.children!.map((c) => (
              <MenuNode key={c.id} item={c} depth={depth + 1} />
            ))}
          </div>
        </>
      ) : target ? (
        <Link className="nav__link" to={target}>
          {item.title}
        </Link>
      ) : (
        <div className="nav__link nav__link--disabled">{item.title}</div>
      )}
    </div>
  );
}

export function Sidebar({ menus }: { menus: MenuItem[] }) {
  return (
    <div className="nav">
      <div className="nav__header">
        <div className="nav__brand">AI PaaS</div>
        <div className="nav__sub">Console</div>
      </div>

      <div className="nav__list">
        {menus.map((m) => (
          <MenuNode key={m.id} item={m} />
        ))}
      </div>
    </div>
  );
}
TSX

# -----------------------------
# 5) plugin CSS
# -----------------------------
cat > "$WEBAPP/styles/plugin.css" <<'CSS'
/* ===== Plugin host (iframe-first) ===== */
.plugin-host {
  height: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.plugin-host__bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
}

.plugin-host__title {
  font-weight: 650;
}

.plugin-host__meta {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  color: var(--muted);
  font-size: var(--text-xs);
}

.pill {
  border: 1px solid var(--border);
  padding: 4px 8px;
  border-radius: 999px;
}

.pill--ok { border-color: rgba(74, 222, 128, 0.35); color: #9af3bf; }
.pill--bad { border-color: rgba(255, 107, 107, 0.35); color: #ffb3b3; }

.plugin-host__frame {
  flex: 1;
  min-height: 0;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  overflow: hidden;
  background: var(--panel);
  box-shadow: var(--shadow-sm);
}

.plugin-iframe {
  width: 100%;
  height: 100%;
  border: 0;
  display: block;
  background: transparent;
}

.plugin-host__error {
  border: 1px solid rgba(255, 107, 107, 0.25);
  background: rgba(255, 107, 107, 0.08);
  color: #ffd0d0;
  padding: var(--space-3);
  border-radius: var(--radius-md);
}

.plugin-host__hint {
  color: var(--muted);
  font-size: var(--text-xs);
}
CSS

# -----------------------------
# 6) Sidebar CSS appended into layout.css (simple)
# -----------------------------
LAYOUT="$WEBAPP/styles/layout.css"
if [ -f "$LAYOUT" ]; then
  if ! grep -q "nav__brand" "$LAYOUT"; then
    cat >> "$LAYOUT" <<'CSS'

/* ===== Sidebar (native shell) ===== */
.nav {
  height: 100%;
  display: flex;
  flex-direction: column;
  padding: var(--space-4);
  gap: var(--space-4);
}

.nav__header { padding-bottom: var(--space-3); border-bottom: 1px solid var(--border); }
.nav__brand { font-weight: 700; letter-spacing: 0.2px; }
.nav__sub { color: var(--muted); font-size: var(--text-xs); margin-top: 4px; }

.nav__list { padding-top: var(--space-2); overflow: auto; }
.nav__group { color: var(--muted); font-size: var(--text-xs); text-transform: uppercase; letter-spacing: 0.12em; padding: 8px 10px; }

.nav__node { border-radius: var(--radius-sm); }
.nav__node--active { background: rgba(110,168,255,0.10); }

.nav__link {
  display: block;
  color: var(--text);
  text-decoration: none;
  padding: 8px 10px;
  border-radius: var(--radius-sm);
}
.nav__link:hover { background: rgba(255,255,255,0.06); }
.nav__link--disabled { color: var(--muted); cursor: not-allowed; }

.nav__children { padding-left: 6px; }
CSS
  fi

  # ensure plugin.css gets loaded: simplest is to append an @import into layout.css (works in Vite)
  if ! grep -q 'styles/plugin.css' "$LAYOUT"; then
    echo '' >> "$LAYOUT"
    echo '@import "./plugin.css";' >> "$LAYOUT"
  fi
fi

chmod +x tools/scaffold_webapp_plugin_runtime.sh

echo "✅ scaffold done."
echo "Next: run your webapp dev server and click iframe menus (flowise/promptflow/langgraph)."
