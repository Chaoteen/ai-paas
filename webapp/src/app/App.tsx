import React, { useEffect, useMemo, useState } from "react";
import { useLocation } from "react-router-dom";
import "../styles/layout.css";
import { Bootstrap, fetchBootstrap } from "../api/bootstrap";
import { Sidebar } from "../components/Sidebar";
import { trackUiEvent } from "../lib/analytics";
import { AppRouter } from "./Router";

export type ControlMenuItem = {
  id: string;
  title: string;
  route?: string;
  permissionKey?: string;
  visible?: boolean;
  enabled?: boolean;
  children?: ControlMenuItem[];
};

function pageMeta(pathname: string): { title: string; subtitle: string } {
  if (pathname.startsWith("/chat")) {
    return {
      title: "对话工作台",
      subtitle: "面向所有人的统一对话入口。",
    };
  }
  if (pathname.startsWith("/skills/recorder")) {
    return {
      title: "录制工作台",
      subtitle: "把人的操作过程蒸馏成可复用技能。",
    };
  }
  if (pathname.startsWith("/skills/library")) {
    return {
      title: "技能库",
      subtitle: "查看、测试、发布和管理技能资产。",
    };
  }
  if (pathname.startsWith("/skills/io-format")) {
    return {
      title: "输入输出格式",
      subtitle: "管理技能与流程的输入输出格式、变量和模板。",
    };
  }
  if (pathname.startsWith("/workflows/designer")) {
    return {
      title: "流程设计器",
      subtitle: "编排技能顺序、条件分支和执行逻辑。",
    };
  }
  if (pathname.startsWith("/workflow/executions")) {
    return {
      title: "执行记录",
      subtitle: "查看流程执行状态、步骤、时间线与异常。",
    };
  }
  if (pathname.startsWith("/workflows/library")) {
    return {
      title: "流程库",
      subtitle: "管理已发布和可复用的流程资产。",
    };
  }
  if (pathname.startsWith("/workers/list")) {
    return {
      title: "数字员工列表",
      subtitle: "查看和管理数字员工资产。",
    };
  }
  if (pathname.startsWith("/workers/config")) {
    return {
      title: "数字员工配置",
      subtitle: "为数字员工绑定技能、流程、模型和运行边界。",
    };
  }
  if (pathname.startsWith("/workers/sessions")) {
    return {
      title: "运行会话",
      subtitle: "查看数字员工执行任务时的会话与状态。",
    };
  }
  if (pathname.startsWith("/opa")) {
    return {
      title: "权限策略",
      subtitle: "配置和调试平台权限策略。",
    };
  }
  if (pathname.startsWith("/admin")) {
    return {
      title: "平台管理",
      subtitle: "面向平台管理员的管理入口。",
    };
  }
  if (pathname.startsWith("/settings")) {
    return {
      title: "系统设置",
      subtitle: "配置系统运行参数和平台设置。",
    };
  }

  return {
    title: "AI PaaS",
    subtitle: "统一控制面。",
  };
}

function isAllowed(boot: Bootstrap | null, permissionKey?: string): boolean {
  if (!permissionKey) return true;
  const capabilities = boot?.capabilities as Record<string, unknown> | undefined;
  if (!capabilities) return true;
  if (!(permissionKey in capabilities)) return true;
  return Boolean(capabilities[permissionKey]);
}

function leaf(
  id: string,
  title: string,
  route: string,
  permissionKey: string,
  boot: Bootstrap | null,
): ControlMenuItem {
  return {
    id,
    title,
    route,
    permissionKey,
    visible: isAllowed(boot, permissionKey),
    enabled: isAllowed(boot, permissionKey),
  };
}

function buildMenus(boot: Bootstrap | null): ControlMenuItem[] {
  return [
    {
      id: "chat-group",
      title: "对话",
      permissionKey: "menu.chat.view",
      visible: isAllowed(boot, "menu.chat.view"),
      enabled: isAllowed(boot, "menu.chat.view"),
      children: [
        leaf("chat", "对话工作台", "/chat", "page.chat.view", boot),
      ],
    },
    {
      id: "skill-group",
      title: "技能录制",
      permissionKey: "menu.skill.view",
      visible: isAllowed(boot, "menu.skill.view"),
      enabled: isAllowed(boot, "menu.skill.view"),
      children: [
        leaf("skill-recorder", "录制工作台", "/skills/recorder", "page.skill.recorder.view", boot),
        leaf("skill-library", "技能库", "/skills/library", "page.skill.library.view", boot),
        leaf("skill-io", "输入输出格式", "/skills/io-format", "page.skill.io_format.view", boot),
      ],
    },
    {
      id: "workflow-group",
      title: "流程编排",
      permissionKey: "menu.workflow.view",
      visible: isAllowed(boot, "menu.workflow.view"),
      enabled: isAllowed(boot, "menu.workflow.view"),
      children: [
        leaf("workflow-designer", "流程设计器", "/workflows/designer", "page.workflow.designer.view", boot),
        leaf("workflow-executions", "执行记录", "/workflow/executions", "page.workflow.executions.view", boot),
        leaf("workflow-library", "流程库", "/workflows/library", "page.workflow.library.view", boot),
      ],
    },
    {
      id: "worker-group",
      title: "数字员工管理",
      permissionKey: "menu.worker.view",
      visible: isAllowed(boot, "menu.worker.view"),
      enabled: isAllowed(boot, "menu.worker.view"),
      children: [
        leaf("worker-list", "数字员工列表", "/workers/list", "page.worker.list.view", boot),
        leaf("worker-config", "数字员工配置", "/workers/config", "page.worker.config.view", boot),
        leaf("worker-sessions", "运行会话", "/workers/sessions", "page.worker.sessions.view", boot),
      ],
    },
    {
      id: "governance-group",
      title: "治理与运维",
      permissionKey: "menu.governance.view",
      visible: isAllowed(boot, "menu.governance.view"),
      enabled: isAllowed(boot, "menu.governance.view"),
      children: [
        leaf("opa", "权限策略", "/opa", "page.policy.view", boot),
        leaf("admin", "平台管理", "/admin", "page.admin.view", boot),
        leaf("settings", "系统设置", "/settings", "page.settings.view", boot),
      ],
    },
  ].filter((group) => group.visible !== false);
}

function buildFallbackBootstrap(): Bootstrap {
  return {
    user: {
      id: "local-user",
      display_name: "Local User",
      is_admin: true,
    },
    tenant: {
      id: "dev",
      name: "Development",
    },
    capabilities: {},
    menus: [],
    layout: {},
    features: {},
  };
}

export function App() {
  const [boot, setBoot] = useState<Bootstrap | null>(null);
  const [bootstrapErr, setBootstrapErr] = useState("");
  const location = useLocation();

  useEffect(() => {
    let alive = true;

    fetchBootstrap()
      .then((data) => {
        if (!alive) return;
        setBoot(data);
        setBootstrapErr("");
      })
      .catch((e) => {
        if (!alive) return;
        setBoot(buildFallbackBootstrap());
        setBootstrapErr(String(e));
      });

    return () => {
      alive = false;
    };
  }, []);

  useEffect(() => {
    if (!boot) return;
    trackUiEvent("page_view", location.pathname, {
      tenant_id: boot.tenant?.id ?? "unknown",
      user_id: boot.user?.id ?? "unknown",
      pathname: location.pathname,
      search: location.search,
    });
  }, [location.pathname, location.search, boot]);

  const menus = useMemo(() => buildMenus(boot), [boot]);

  const currentPage = useMemo(
    () => pageMeta(location.pathname),
    [location.pathname],
  );

  const tenantLabel = boot?.tenant?.name || boot?.tenant?.id || "unknown";
  const userLabel = boot?.user?.display_name || boot?.user?.id || "unknown";

  if (!boot) {
    return <div className="app-loading">Loading...</div>;
  }

  return (
    <div className="shell">
      <aside className="shell__sidebar">
        <Sidebar
          menus={menus}
          tenantId={boot.tenant?.id ?? "unknown"}
          userId={boot.user?.id ?? "unknown"}
        />
      </aside>

      <section className="shell__workspace">
        <header className="workspace__topbar">
          <div className="workspace__topbarLeft">
            <div className="workspace__pageTitleBlock">
              <div className="workspace__pageTitle">{currentPage.title}</div>
              <div className="workspace__pageSubtitle">{currentPage.subtitle}</div>
            </div>
          </div>

          <div className="workspace__topbarRight">
            <div className="workspace__metaTag">Tenant: {tenantLabel}</div>
            <div className="workspace__metaTag">User: {userLabel}</div>
            <button
              className="workspace__logoutBtn"
              onClick={() => {
                trackUiEvent("button_click", location.pathname, {
                  tenant_id: boot.tenant?.id ?? "unknown",
                  user_id: boot.user?.id ?? "unknown",
                  button: "logout",
                });
                alert("TODO: logout");
              }}
            >
              Logout
            </button>
          </div>
        </header>

        {bootstrapErr ? (
          <div className="workspace__warning">
            Bootstrap fallback mode: {bootstrapErr}
          </div>
        ) : null}

        <main className="workspace__content">
          <AppRouter defaultTenantId={boot.tenant?.id ?? "dev"} />
        </main>
      </section>
    </div>
  );
}