import React, { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  WorkflowExecutionDetailResponse,
  getWorkflowExecutionDetail,
} from "../api/workflowExecutions";
import "../styles/workflow-executions.css";

function formatDateTime(value?: string | null): string {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}

function JsonBlock({
  title,
  value,
}: {
  title: string;
  value: unknown;
}) {
  return (
    <div className="wf-card">
      <div className="wf-card__header">
        <h3 className="wf-card__title">{title}</h3>
      </div>
      <pre className="wf-json">{JSON.stringify(value ?? {}, null, 2)}</pre>
    </div>
  );
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

export default function WorkflowExecutionDetail() {
  const { workflowExecutionId = "" } = useParams();
  const [detail, setDetail] = useState<WorkflowExecutionDetailResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");

  useEffect(() => {
    let alive = true;

    async function load() {
      setLoading(true);
      setErr("");
      try {
        const body = await getWorkflowExecutionDetail(workflowExecutionId);
        if (!alive) return;
        setDetail(body);
      } catch (e) {
        if (!alive) return;
        setErr(String(e));
      } finally {
        if (alive) setLoading(false);
      }
    }

    void load();
    return () => {
      alive = false;
    };
  }, [workflowExecutionId]);

  if (loading) {
    return <div className="wf-empty">Loading execution detail...</div>;
  }

  if (err) {
    return <div className="wf-error">{err}</div>;
  }

  if (!detail) {
    return <div className="wf-empty">Execution detail not found.</div>;
  }

  const { execution, steps, timeline, summary } = detail;

  return (
    <div className="wf-page">
      <div className="wf-page__header">
        <div>
          <div className="wf-breadcrumb">
            <Link className="wf-link" to={`/workflow/executions?tenant_id=${execution.tenant_id}`}>
              Workflow Executions
            </Link>
            <span>/</span>
            <span>{execution.workflow_execution_id}</span>
          </div>
          <h1 className="wf-page__title">Workflow Execution Detail</h1>
          <p className="wf-page__subtitle">
            观察 execution、steps、timeline 和原始 input/context/output。
          </p>
        </div>
        <div className="wf-detail-status">
          <span className={statusClass(execution.status)}>{execution.status}</span>
        </div>
      </div>

      <div className="wf-summary-grid">
        <div className="wf-summary-card">
          <div className="wf-summary-card__label">Workflow</div>
          <div className="wf-summary-card__value wf-summary-card__value--small">
            {execution.workflow_key}
          </div>
        </div>
        <div className="wf-summary-card">
          <div className="wf-summary-card__label">Version</div>
          <div className="wf-summary-card__value">v{execution.workflow_version}</div>
        </div>
        <div className="wf-summary-card">
          <div className="wf-summary-card__label">Steps</div>
          <div className="wf-summary-card__value">{summary.step_count}</div>
        </div>
        <div className="wf-summary-card">
          <div className="wf-summary-card__label">Events</div>
          <div className="wf-summary-card__value">{summary.event_count}</div>
        </div>
      </div>

      <div className="wf-card">
        <div className="wf-card__header">
          <h2 className="wf-card__title">Execution Overview</h2>
        </div>
        <div className="wf-overview-grid">
          <div><strong>Execution ID:</strong> <span className="wf-mono">{execution.workflow_execution_id}</span></div>
          <div><strong>Task ID:</strong> <span className="wf-mono">{execution.task_id}</span></div>
          <div><strong>Tenant:</strong> {execution.tenant_id}</div>
          <div><strong>Status:</strong> {execution.status}</div>
          <div><strong>Created:</strong> {formatDateTime(execution.created_at)}</div>
          <div><strong>Started:</strong> {formatDateTime(execution.started_at)}</div>
          <div><strong>Finished:</strong> {formatDateTime(execution.finished_at)}</div>
          <div><strong>Active Nodes:</strong> {execution.active_node_ids.join(", ") || "-"}</div>
          {execution.error_text ? (
            <div className="wf-error wf-error--inline">
              <strong>Error:</strong> {execution.error_text}
            </div>
          ) : null}
        </div>
      </div>

      <div className="wf-card">
        <div className="wf-card__header">
          <h2 className="wf-card__title">Step Attempts</h2>
        </div>
        {steps.length === 0 ? (
          <div className="wf-empty">No steps found.</div>
        ) : (
          <div className="wf-table-wrap">
            <table className="wf-table">
              <thead>
                <tr>
                  <th>Node</th>
                  <th>Status</th>
                  <th>Attempt</th>
                  <th>Started</th>
                  <th>Finished</th>
                  <th>Error</th>
                </tr>
              </thead>
              <tbody>
                {steps.map((step) => (
                  <tr key={step.workflow_step_execution_id}>
                    <td>
                      <div className="wf-key">
                        <div className="wf-key__main">{step.node_id}</div>
                        <div className="wf-key__sub">{step.node_type}</div>
                      </div>
                    </td>
                    <td>
                      <span className={statusClass(step.status)}>{step.status}</span>
                    </td>
                    <td>{step.attempt_no}</td>
                    <td>{formatDateTime(step.started_at || step.created_at)}</td>
                    <td>{formatDateTime(step.finished_at)}</td>
                    <td>{step.error_text || "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="wf-card">
        <div className="wf-card__header">
          <h2 className="wf-card__title">Execution Timeline</h2>
        </div>
        {timeline.length === 0 ? (
          <div className="wf-empty">No timeline items found.</div>
        ) : (
          <div className="wf-timeline">
            {timeline.map((item) => (
              <div key={`${item.sequence_no}-${item.event_type}`} className="wf-timeline__item">
                <div className="wf-timeline__seq">#{item.sequence_no}</div>
                <div className="wf-timeline__content">
                  <div className="wf-timeline__top">
                    <span className="wf-timeline__event">{item.event_type}</span>
                    <span className="wf-timeline__time">{formatDateTime(item.created_at)}</span>
                  </div>
                  <div className="wf-timeline__meta">
                    <span>lane: {item.lane}</span>
                    {item.node_id ? <span>node: {item.node_id}</span> : null}
                    {item.status ? <span>status: {item.status}</span> : null}
                    {item.workflow_step_execution_id ? (
                      <span className="wf-mono">
                        step_execution_id: {item.workflow_step_execution_id}
                      </span>
                    ) : null}
                  </div>
                  <pre className="wf-json wf-json--compact">
                    {JSON.stringify(item.payload_json ?? {}, null, 2)}
                  </pre>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="wf-detail-grid">
        <JsonBlock title="Input JSON" value={execution.input_json} />
        <JsonBlock title="Context JSON" value={execution.context_json} />
        <JsonBlock title="Output JSON" value={execution.output_json} />
        <JsonBlock title="System Context JSON" value={execution.system_context_json} />
      </div>
    </div>
  );
}