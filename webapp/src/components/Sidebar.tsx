import React from "react";
import { NavLink, useLocation } from "react-router-dom";
import type { ControlMenuItem } from "../app/App";
import { trackUiEvent } from "../lib/analytics";

function SidebarLeaf({
  item,
  tenantId,
  userId,
}: {
  item: ControlMenuItem;
  tenantId: string;
  userId: string;
}) {
  const location = useLocation();
  const disabled = item.enabled === false || !item.route;

  if (disabled) {
    return (
      <div className="sidebar__item sidebar__item--disabled">
        <span className="sidebar__itemText">{item.title}</span>
      </div>
    );
  }

  return (
    <NavLink
      to={item.route!}
      className={({ isActive }) =>
        `sidebar__item sidebar__item--child ${isActive ? "sidebar__item--active" : ""}`
      }
      onClick={() => {
        trackUiEvent("menu_click", location.pathname, {
          tenant_id: tenantId,
          user_id: userId,
          menu_id: item.id,
          menu_title: item.title,
          route: item.route,
          permission_key: item.permissionKey || "",
          level: 2,
        });
      }}
    >
      <span className="sidebar__itemText">{item.title}</span>
    </NavLink>
  );
}

function SidebarGroup({
  item,
  tenantId,
  userId,
}: {
  item: ControlMenuItem;
  tenantId: string;
  userId: string;
}) {
  const location = useLocation();
  const children = (item.children || []).filter((child) => child.visible !== false);

  return (
    <div className="sidebar__group">
      <div
        className="sidebar__groupTitle"
        onClick={() => {
          trackUiEvent("menu_group_view", location.pathname, {
            tenant_id: tenantId,
            user_id: userId,
            menu_id: item.id,
            menu_title: item.title,
            permission_key: item.permissionKey || "",
            level: 1,
          });
        }}
      >
        {item.title}
      </div>

      <div className="sidebar__groupBody">
        {children.map((child) => (
          <SidebarLeaf
            key={child.id}
            item={child}
            tenantId={tenantId}
            userId={userId}
          />
        ))}
      </div>
    </div>
  );
}

export function Sidebar({
  menus,
  tenantId,
  userId,
}: {
  menus: ControlMenuItem[];
  tenantId: string;
  userId: string;
}) {
  return (
    <div className="sidebar">
      <div className="sidebar__header">
        <div className="sidebar__brand">AI PaaS</div>
        <div className="sidebar__brandSub">Control Plane</div>
      </div>

      <div className="sidebar__scroll">
        {menus && menus.length > 0 ? (
          menus.map((item) => (
            <SidebarGroup
              key={item.id}
              item={item}
              tenantId={tenantId}
              userId={userId}
            />
          ))
        ) : (
          <div className="sidebar__empty">No menus</div>
        )}
      </div>
    </div>
  );
}