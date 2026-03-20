import { useMemo, useState } from "react";

type HttpMethod = "GET" | "POST";

type ApiResult = {
  ok: boolean;
  status: number;
  body: any;
};

type SubmitResponse = {
  task_id: string;
  status: string;
  queue_name: string;
  stream_name: string;
  durable: boolean;
  outbox_event_id: number;
};

const DEFAULT_BASE_URL =
  (import.meta as any)?.env?.VITE_API_BASE_URL?.replace(/\/$/, "") ||
  "http://127.0.0.1:8000";

async function apiCall(
  baseUrl: string,
  method: HttpMethod,
  path: string,
  payload?: unknown
): Promise<ApiResult> {
  const response = await fetch(`${baseUrl}${path}`, {
    method,
    headers: {
      "Content-Type": "application/json",
    },
    body: method === "POST" ? JSON.stringify(payload ?? {}) : undefined,
  });

  let body: any = null;
  try {
    body = await response.json();
  } catch {
    body = null;
  }

  return {
    ok: response.ok,
    status: response.status,
    body,
  };
}

function pretty(value: unknown): string {
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

export default function App() {
  const [baseUrl, setBaseUrl] = useState(DEFAULT_BASE_URL);
  const [activeTab, setActiveTab] = useState<
    "dashboard" | "agent" | "image" | "video" | "tasks" | "health"
  >("dashboard");

  const [tenantId, setTenantId] = useState("dev");
  const [model, setModel] = useState("qwen");
  const [prompt, setPrompt] = useState("Hello from Phase 17");
  const [systemPrompt, setSystemPrompt] = useState("");
  const [temperature, setTemperature] = useState("0.7");
  const [maxTokens, setMaxTokens] = useState("256");
  const [size, setSize] = useState("1024x1024");
  const [durationSeconds, setDurationSeconds] = useState("5");
  const [taskId, setTaskId] = useState("");

  const [lastResponse, setLastResponse] = useState<any>(null);
  const [lastError, setLastError] = useState<string>("");
  const [isLoading, setIsLoading] = useState(false);

  const navItems = useMemo(
    () => [
      ["dashboard", "Dashboard"],
      ["agent", "Agent Run / Submit"],
      ["image", "Image Generation"],
      ["video", "Video Generation"],
      ["tasks", "Task Query"],
      ["health", "Health"],
    ] as const,
    []
  );

  async function handleRequest(
    method: HttpMethod,
    path: string,
    payload?: unknown,
    autoCaptureTaskId = true
  ) {
    setIsLoading(true);
    setLastError("");
    try {
      const result = await apiCall(baseUrl, method, path, payload);
      setLastResponse(result);

      if (!result.ok) {
        setLastError(
          result.body?.detail
            ? String(result.body.detail)
            : `Request failed with status ${result.status}`
        );
      }

      if (autoCaptureTaskId && result.ok && result.body?.task_id) {
        setTaskId(result.body.task_id);
      }
    } catch (error: any) {
      setLastError(error?.message || "Unknown request error");
      setLastResponse(null);
    } finally {
      setIsLoading(false);
    }
  }

  async function pollTaskStatus() {
    if (!taskId.trim()) {
      setLastError("Please enter task id");
      return;
    }
    await handleRequest("GET", `/api/v1/tasks/${taskId.trim()}`, undefined, false);
  }

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-title">AI-PaaS</div>
          <div className="brand-subtitle">Phase 17 Console</div>
        </div>

        <nav className="nav">
          {navItems.map(([key, label]) => (
            <button
              key={key}
              className={`nav-item ${activeTab === key ? "active" : ""}`}
              onClick={() => setActiveTab(key)}
            >
              {label}
            </button>
          ))}
        </nav>
      </aside>

      <main className="content">
        <header className="topbar">
          <div>
            <div className="page-title">Runtime Mainline Console</div>
            <div className="page-subtitle">
              Durable submit path + task query + minimal ops UI
            </div>
          </div>

          <div className="base-url-box">
            <label>API Base URL</label>
            <input
              value={baseUrl}
              onChange={(e) => setBaseUrl(e.target.value)}
              placeholder="http://127.0.0.1:8000"
            />
          </div>
        </header>

        <section className="grid two">
          <div className="card">
            <h3>Shared Request Inputs</h3>

            <div className="form-grid">
              <label>
                Tenant ID
                <input value={tenantId} onChange={(e) => setTenantId(e.target.value)} />
              </label>

              <label>
                Model
                <input value={model} onChange={(e) => setModel(e.target.value)} />
              </label>

              <label className="full">
                Prompt
                <textarea
                  rows={5}
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                />
              </label>

              <label className="full">
                System Prompt
                <textarea
                  rows={3}
                  value={systemPrompt}
                  onChange={(e) => setSystemPrompt(e.target.value)}
                />
              </label>

              <label>
                Temperature
                <input
                  value={temperature}
                  onChange={(e) => setTemperature(e.target.value)}
                />
              </label>

              <label>
                Max Tokens
                <input
                  value={maxTokens}
                  onChange={(e) => setMaxTokens(e.target.value)}
                />
              </label>

              <label>
                Image Size
                <input value={size} onChange={(e) => setSize(e.target.value)} />
              </label>

              <label>
                Video Duration
                <input
                  value={durationSeconds}
                  onChange={(e) => setDurationSeconds(e.target.value)}
                />
              </label>
            </div>
          </div>

          <div className="card">
            <h3>Task Query</h3>

            <div className="form-grid">
              <label className="full">
                Task ID
                <input value={taskId} onChange={(e) => setTaskId(e.target.value)} />
              </label>
            </div>

            <div className="button-row">
              <button onClick={pollTaskStatus} disabled={isLoading}>
                Query Task
              </button>
            </div>

            <div className="hint">
              Submit APIs will auto-fill task_id here when the response contains one.
            </div>
          </div>
        </section>

        {activeTab === "dashboard" && (
          <section className="card">
            <h3>Dashboard</h3>
            <p>
              This console is the Phase 17 minimal runtime UI. It is focused on the
              formal mainline:
            </p>
            <pre className="code-block">
Gateway API
→ TaskSubmissionService
→ runtime_tasks / runtime_outbox_events
→ OutboxRelay
→ Redis Queue
→ Worker Runtime
→ Runtime Services
            </pre>
            <div className="button-row">
              <button
                onClick={() => handleRequest("GET", "/api/health")}
                disabled={isLoading}
              >
                Check API Health
              </button>
            </div>
          </section>
        )}

        {activeTab === "agent" && (
          <section className="card">
            <h3>Agent Run / Submit</h3>
            <div className="button-row">
              <button
                disabled={isLoading}
                onClick={() =>
                  handleRequest("POST", "/api/v1/agent/run", {
                    tenant_id: tenantId,
                    prompt,
                    model,
                    system_prompt: systemPrompt || undefined,
                    temperature: Number(temperature),
                    max_tokens: Number(maxTokens),
                  })
                }
              >
                Agent Run
              </button>

              <button
                disabled={isLoading}
                onClick={() =>
                  handleRequest("POST", "/api/v1/agent/submit", {
                    tenant_id: tenantId,
                    prompt,
                    model,
                    system_prompt: systemPrompt || undefined,
                    temperature: Number(temperature),
                    max_tokens: Number(maxTokens),
                    metadata: { source: "webapp-phase17" },
                  })
                }
              >
                Agent Submit
              </button>
            </div>
          </section>
        )}

        {activeTab === "image" && (
          <section className="card">
            <h3>Image Generation</h3>
            <div className="button-row">
              <button
                disabled={isLoading}
                onClick={() =>
                  handleRequest("POST", "/api/v1/generation/image", {
                    tenant_id: tenantId,
                    prompt,
                    model,
                    size,
                  })
                }
              >
                Image Run
              </button>

              <button
                disabled={isLoading}
                onClick={() =>
                  handleRequest("POST", "/api/v1/generation/image/submit", {
                    tenant_id: tenantId,
                    prompt,
                    model,
                    size,
                    metadata: { source: "webapp-phase17" },
                  })
                }
              >
                Image Submit
              </button>
            </div>
          </section>
        )}

        {activeTab === "video" && (
          <section className="card">
            <h3>Video Generation</h3>
            <div className="button-row">
              <button
                disabled={isLoading}
                onClick={() =>
                  handleRequest("POST", "/api/v1/generation/video", {
                    tenant_id: tenantId,
                    prompt,
                    model,
                    duration_seconds: Number(durationSeconds),
                  })
                }
              >
                Video Run
              </button>

              <button
                disabled={isLoading}
                onClick={() =>
                  handleRequest("POST", "/api/v1/generation/video/submit", {
                    tenant_id: tenantId,
                    prompt,
                    model,
                    duration_seconds: Number(durationSeconds),
                    metadata: { source: "webapp-phase17" },
                  })
                }
              >
                Video Submit
              </button>
            </div>
          </section>
        )}

        {activeTab === "tasks" && (
          <section className="card">
            <h3>Task Console</h3>
            <div className="button-row">
              <button onClick={pollTaskStatus} disabled={isLoading}>
                Refresh Task Status
              </button>
            </div>
            <div className="hint">
              Recommended flow: submit → auto capture task_id → refresh here.
            </div>
          </section>
        )}

        {activeTab === "health" && (
          <section className="card">
            <h3>Health</h3>
            <div className="button-row">
              <button
                onClick={() => handleRequest("GET", "/api/health")}
                disabled={isLoading}
              >
                Gateway Health
              </button>
            </div>
          </section>
        )}

        <section className="grid two">
          <div className="card">
            <h3>Request Status</h3>
            <div className="status-line">
              <span>Loading:</span>
              <strong>{isLoading ? "yes" : "no"}</strong>
            </div>
            <div className="status-line">
              <span>Last Error:</span>
              <strong className={lastError ? "danger" : ""}>
                {lastError || "none"}
              </strong>
            </div>
          </div>

          <div className="card">
            <h3>Last Response</h3>
            <pre className="response-block">{pretty(lastResponse)}</pre>
          </div>
        </section>
      </main>
    </div>
  );
}