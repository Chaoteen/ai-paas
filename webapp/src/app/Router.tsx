import React from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { OpaConsole } from "../pages/OpaConsole";
import { Admin } from "../pages/Admin";
import Settings from "../pages/Settings";
import Chat from "../pages/chat";
import WorkflowExecutions from "../pages/WorkflowExecutions";
import WorkflowExecutionDetail from "../pages/WorkflowExecutionDetail";
import { trackUiEvent } from "../lib/analytics";

function PlaceholderPage({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap: 12,
      }}
    >
      <div
        style={{
          fontSize: 28,
          fontWeight: 700,
        }}
      >
        {title}
      </div>

      <div
        style={{
          fontSize: 14,
          color: "var(--muted)",
          maxWidth: 820,
          lineHeight: 1.7,
        }}
      >
        {description}
      </div>

      <div
        style={{
          marginTop: 8,
          padding: 16,
          borderRadius: 12,
          border: "1px solid var(--border)",
          background: "var(--panel-bg)",
          color: "var(--text)",
          fontSize: 13,
          lineHeight: 1.7,
        }}
      >
        当前页面为业务骨架页。后续这里会替换成正式产品能力页面。
      </div>
    </div>
  );
}

function TrackedPlaceholder({
  page,
  title,
  description,
}: {
  page: string;
  title: string;
  description: string;
}) {
  React.useEffect(() => {
    trackUiEvent("page_ready", page, {
      page_title: title,
    });
  }, [page, title]);

  return <PlaceholderPage title={title} description={description} />;
}

export function AppRouter({ defaultTenantId = "dev" }: { defaultTenantId?: string }) {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/chat" replace />} />

      <Route path="/chat" element={<Chat />} />

      <Route
        path="/skills/recorder"
        element={
          <TrackedPlaceholder
            page="/skills/recorder"
            title="录制工作台"
            description="把人的操作过程录制下来，抽取为可复用技能。这里后续会接入桌面/网页操作录制与参数化能力。"
          />
        }
      />
      <Route
        path="/skills/library"
        element={
          <TrackedPlaceholder
            page="/skills/library"
            title="技能库"
            description="查看、筛选、测试、发布和管理技能资产。"
          />
        }
      />
      <Route
        path="/skills/io-format"
        element={
          <TrackedPlaceholder
            page="/skills/io-format"
            title="输入输出格式"
            description="定义技能与流程的输入输出格式、变量映射和模板规范。"
          />
        }
      />

      <Route
        path="/workflows/designer"
        element={
          <TrackedPlaceholder
            page="/workflows/designer"
            title="流程设计器"
            description="编排技能执行顺序、分支逻辑、输入输出传递和异常处理。"
          />
        }
      />
      <Route
        path="/workflow/executions"
        element={<WorkflowExecutions defaultTenantId={defaultTenantId} />}
      />
      <Route
        path="/workflow/executions/:workflowExecutionId"
        element={<WorkflowExecutionDetail />}
      />
      <Route
        path="/workflows/library"
        element={
          <TrackedPlaceholder
            page="/workflows/library"
            title="流程库"
            description="统一查看、管理、发布和复用流程资产。"
          />
        }
      />

      <Route
        path="/workers/list"
        element={
          <TrackedPlaceholder
            page="/workers/list"
            title="数字员工列表"
            description="查看已创建的数字员工，并为后续上架市场和租户内分发做资产管理准备。"
          />
        }
      />
      <Route
        path="/workers/config"
        element={
          <TrackedPlaceholder
            page="/workers/config"
            title="数字员工配置"
            description="为数字员工绑定技能、流程、模型和运行边界。"
          />
        }
      />
      <Route
        path="/workers/sessions"
        element={
          <TrackedPlaceholder
            page="/workers/sessions"
            title="运行会话"
            description="查看数字员工运行中的会话、任务状态、结果和异常。"
          />
        }
      />

      <Route path="/opa" element={<OpaConsole />} />
      <Route path="/admin" element={<Admin />} />
      <Route path="/settings" element={<Settings />} />

      <Route path="*" element={<Navigate to="/chat" replace />} />
    </Routes>
  );
}