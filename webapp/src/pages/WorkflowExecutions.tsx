import React, { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  WorkflowExecution,
  listWorkflowExecutions,
} from "../api/workflowExecutions";
import "../styles/workflow-executions.css";

type Props = {
  defaultTenantId?: string;
};

function formatDateTime(value?: string | null): string {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}

function statusClass(status: string): string {
  switch (status) {
    case "succeeded":
      return "wf-status wf-status--success";
    case "failed":
      return "wf-status wf-status--failed";
    case "running":
      return "wf-status wf-status--running";
    default:
      return "wf-status wf-status--neutral";
  }
}

export default function WorkflowExecutions({ defaultTenantId = "dev" }: Props) {
  const [searchParams, setSearchParams] = useSearchParams();
  const initialTenant = searchParams.get("tenant_id") || defaultTenantId;

  const [tenantId, setTenantId] = useState(initialTenant);
  const [items, setItems] = useState<WorkflowExecution[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");

  useEffect(() => {
    let alive = true;

    async function load() {
      setLoading(true);
      setErr("");
      try {
        const body = await listWorkflowExecutions(tenantId);
        if (!alive) return;
        setItems(body.items);
      } catch (e) {
        if (!alive) return;
        setErr(String(e));
      } finally {
        if (alive) setLoading(false);
      }
    }

    const nextParams = new URLSearchParams(searchParams);
    nextParams.set("tenant_id", tenantId);
    setSearchParams(nextParams, { replace: true });

    void load();
    return () => {
      alive = false;
    };
  }, [tenantId]);

  const summary = useMemo(() => {
    const total = items.length;
    const succeeded = items.filter((item) => item.status === "succeeded").length;
    const failed = items.filter((item) => item.status === "failed").length;
    const running = items.filter((item) => item.status === "running").length;
    return { total, succeeded, failed, running };
  }, [items]);

  return (
    <div className="wf-page">
      <div className="wf-page__header">
        <div>
          <h1 className="wf-page__title">Workflow Executions</h1>
          <p className="wf-page__subtitle">
            面向平台控制面的执行观察列表。按租户查看 workflow execution、task 状态和进入详情页。
          </p>
        </div>

        <div className="wf-toolbar">
          <label className="wf-field">
            <span className="wf-field__label">Tenant</span>
            <input
              className="wf-input"
              value={tenantId}
              onChange={(e) => setTenantId(e.target.value)}
              placeholder="dev"
            />
          </label>
        </div>
      </div>

      <div className="wf-summary-grid">
        <div className="wf-summary-card">
          <div className="wf-summary-card__label">Total</div>
          <div className="wf-summary-card__value">{summary.total}</div>
        </div>
        <div className="wf-summary-card">
          <div className="wf-summary-card__label">Succeeded</div>
          <div className="wf-summary-card__value">{summary.succeeded}</div>
        </div>
        <div className="wf-summary-card">
          <div className="wf-summary-card__label">Failed</div>
          <div className="wf-summary-card__value">{summary.failed}</div>
        </div>
        <div className="wf-summary-card">
          <div className="wf-summary-card__label">Running</div>
          <div className="wf-summary-card__value">{summary.running}</div>
        </div>
      </div>

      {err ? <div className="wf-error">{err}</div> : null}

      <div className="wf-card">
        <div className="wf-card__header">
          <h2 className="wf-card__title">Execution List</h2>
          <button className="wf-button" onClick={() => setTenantId(tenantId)}>
            Refresh
          </button>
        </div>

        {loading ? (
          <div className="wf-empty">Loading executions...</div>
        ) : items.length === 0 ? (
          <div className="wf-empty">No workflow executions found for tenant: {tenantId}</div>
        ) : (
          <div className="wf-table-wrap">
            <table className="wf-table">
              <thead>
                <tr>
                  <th>Status</th>
                  <th>Workflow</th>
                  <th>Task ID</th>
                  <th>Execution ID</th>
                  <th>Started</th>
                  <th>Finished</th>
                  <th>Detail</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr key={item.workflow_execution_id}>
                    <td>
                      <span className={statusClass(item.status)}>{item.status}</span>
                    </td>
                    <td>
                      <div className="wf-key">
                        <div className="wf-key__main">{item.workflow_key}</div>
                        <div className="wf-key__sub">v{item.workflow_version}</div>
                      </div>
                    </td>
                    <td className="wf-mono">{item.task_id}</td>
                    <td className="wf-mono">{item.workflow_execution_id}</td>
                    <td>{formatDateTime(item.started_at || item.created_at)}</td>
                    <td>{formatDateTime(item.finished_at)}</td>
                    <td>
                      <Link
                        className="wf-link"
                        to={`/workflow/executions/${item.workflow_execution_id}`}
                      >
                        View detail
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}