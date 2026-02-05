import React from "react";
import { Link, useLocation } from "react-router-dom";
import { MenuItem } from "../api/bootstrap";

function isActive(pathname: string, route: string): boolean {
  if (!route) return false;
  if (route === "/") return pathname === "/";
  return pathname === route || pathname.startsWith(route + "/");
}

function MenuNode({ item }: { item: MenuItem }) {
  const loc = useLocation();
  const hasChildren = (item.children?.length || 0) > 0;

  if (hasChildren) {
    return (
      <div style={{ marginBottom: 10 }}>
        <div style={{ fontWeight: 650, padding: "8px 10px" }}>
          {item.title}
        </div>
        <div style={{ paddingLeft: 10 }}>
          {item.children!.map((c) => (
            <MenuNode key={c.id} item={c} />
          ))}
        </div>
      </div>
    );
  }

  const isIframe = item.type === "iframe" || Boolean((item as any).url);

  // 🔥 关键：iframe 一律走 /plugins/:id
  const route = isIframe
    ? `/plugins/${item.id}`
    : item.route || `/menu/${item.id}`;

  const active = isIframe
    ? loc.pathname.startsWith(`/plugins/${item.id}`)
    : isActive(loc.pathname, item.route || "");

  return (
    <div style={{ padding: "4px 6px" }}>
      <Link
        to={route}
        style={{
          display: "block",
          textDecoration: "none",
          padding: "8px 10px",
          borderRadius: 10,
          background: active ? "rgba(110,168,255,0.12)" : "transparent",
        }}
      >
        {item.title}
      </Link>
    </div>
  );
}

export function Sidebar({ menus }: { menus: MenuItem[] }) {
  return (
    <div style={{ padding: 10 }}>
      {menus.map((m) => (
        <MenuNode key={m.id} item={m} />
      ))}
    </div>
  );
}
