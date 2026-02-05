import React from "react";
import { Link, useLocation } from "react-router-dom";
import { MenuItem } from "../api/bootstrap";

function toPluginRoute(title: string, url: string): string {
  const sp = new URLSearchParams();
  sp.set("title", title || "Plugin");
  sp.set("url", url);
  return `/plugin?${sp.toString()}`;
}

function isActive(pathname: string, route: string): boolean {
  if (!route) return false;
  if (route === "/") return pathname === "/";
  return pathname === route || pathname.startsWith(route + "/");
}

function MenuNode({ item, depth }: { item: MenuItem; depth: number }) {
  const loc = useLocation();
  const hasChildren = (item.children?.length || 0) > 0;

  // group node
  if (hasChildren) {
    return (
      <div style={{ marginBottom: 10 }}>
        <div
          style={{
            fontWeight: 650,
            padding: "8px 10px",
            color: "var(--text)",
            opacity: 0.9,
          }}
        >
          {item.title}
        </div>
        <div style={{ paddingLeft: 10 }}>
          {item.children!.map((c) => (
            <MenuNode key={c.id} item={c} depth={depth + 1} />
          ))}
        </div>
      </div>
    );
  }

  // leaf node
  const isIframe = item.type === "iframe" || Boolean(item.url);
  const route = isIframe
    ? toPluginRoute(item.title || item.id, item.url || "")
    : item.route || `/menu/${item.id}`;

  const active = isActive(loc.pathname, item.route || "");

  return (
    <div style={{ padding: "4px 6px" }}>
      <Link
        to={route}
        style={{
          display: "block",
          textDecoration: "none",
          color: "var(--text)",
          padding: "8px 10px",
          borderRadius: 10,
          border: "1px solid transparent",
          background: active ? "rgba(110,168,255,0.12)" : "transparent",
        }}
      >
        <div style={{ fontSize: "var(--text-sm)", lineHeight: 1.2 }}>
          {item.title}
        </div>
        {isIframe ? (
          <div style={{ fontSize: "var(--text-xs)", color: "var(--muted)", marginTop: 3 }}>
            iframe
          </div>
        ) : null}
      </Link>
    </div>
  );
}

export function Sidebar({ menus }: { menus: MenuItem[] }) {
  return (
    <div style={{ padding: 10 }}>
      {menus.map((m) => (
        <MenuNode key={m.id} item={m} depth={0} />
      ))}
    </div>
  );
}
