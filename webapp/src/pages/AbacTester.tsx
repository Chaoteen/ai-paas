import React, { useMemo, useState } from "react";
import { opaEvalUiAllow } from "../api/opa";

function pretty(v: any) {
  try {
    return JSON.stringify(v, null, 2);
  } catch {
    return String(v);
  }
}

export function AbacTester() {
  const [resourceType, setResourceType] = useState("menu");
  const [resourceId, setResourceId] = useState("workflows");

  const [isAdmin, setIsAdmin] = useState(true);

  // 你现在 JWT 里强依赖 tenant_id，所以这里也带上，方便你后续扩展到更多策略维度
  const [tenantId, setTenantId] = useState(localStorage.getItem("AI_PAAS_TENANT") || "tenant_a");
  const [userId, setUserId] = useState(localStorage.getItem("AI_PAAS_USER") || "admin_a");

  const [loading, setLoading] = useState(false);
  const [resp, setResp] = useState<any>(null);
  const [err, setErr] = useState("");

  const inputDoc = useMemo(
    () => ({
      resource: { type: resourceType.trim(), id: resourceId.trim() },
      subject: {
        is_admin: isAdmin,
        tenant_id: tenantId.trim(),
        user_id: userId.trim(),
      },
    }),
    [resourceType, resourceId, isAdmin, tenantId, userId]
  );

  async function run() {
    setErr("");
    setResp(null);
    setLoading(true);
    try {
      const out = await opaEvalUiAllow(inputDoc);
      setResp(out);
    } catch (e: any) {
      setErr(String(e?.message || e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{ display: "grid", gridTemplateColumns: "420px 1fr", gap: 16 }}>
      <div style={{ border: "1px solid var(--border)", borderRadius: 12, padding: 12, background: "var(--panel)" }}>
        <div style={{ fontWeight: 650, marginBottom: 10 }}>OPA 决策测试</div>

        <div style={{ display: "grid", gap: 10 }}>
          <label style={{ display: "grid", gap: 6 }}>
            <div style={{ fontSize: "var(--text-sm)", color: "var(--muted)" }}>resource.type</div>
            <input
              value={resourceType}
              onChange={(e) => setResourceType(e.target.value)}
              style={inputStyle}
              placeholder="menu"
            />
          </label>

          <label style={{ display: "grid", gap: 6 }}>
            <div style={{ fontSize: "var(--text-sm)", color: "var(--muted)" }}>resource.id</div>
            <input
              value={resourceId}
              onChange={(e) => setResourceId(e.target.value)}
              style={inputStyle}
              placeholder="workflows / admin / chat ..."
            />
          </label>

          <label style={{ display: "flex", gap: 10, alignItems: "center" }}>
            <input type="checkbox" checked={isAdmin} onChange={(e) => setIsAdmin(e.target.checked)} />
            <span style={{ fontSize: "var(--text-sm)" }}>subject.is_admin</span>
          </label>

          <label style={{ display: "grid", gap: 6 }}>
            <div style={{ fontSize: "var(--text-sm)", color: "var(--muted)" }}>subject.tenant_id</div>
            <input value={tenantId} onChange={(e) => setTenantId(e.target.value)} style={inputStyle} />
          </label>

          <label style={{ display: "grid", gap: 6 }}>
            <div style={{ fontSize: "var(--text-sm)", color: "var(--muted)" }}>subject.user_id</div>
            <input value={userId} onChange={(e) => setUserId(e.target.value)} style={inputStyle} />
          </label>

          <button className="btn" type="button" onClick={run} disabled={loading}>
            {loading ? "Running..." : "Run decision"}
          </button>

          <div style={{ fontSize: "var(--text-xs)", color: "var(--muted)" }}>
            调用：<code>/opa-api/v1/data/ui/allow</code>
          </div>
        </div>
      </div>

      <div style={{ border: "1px solid var(--border)", borderRadius: 12, overflow: "hidden" }}>
        <div style={{ padding: 10, borderBottom: "1px solid var(--border)", background: "var(--panel)" }}>
          <div style={{ fontWeight: 650 }}>Input</div>
        </div>
        <pre style={preStyle}>{pretty({ input: inputDoc })}</pre>

        <div style={{ padding: 10, borderTop: "1px solid var(--border)", borderBottom: "1px solid var(--border)", background: "var(--panel)" }}>
          <div style={{ fontWeight: 650 }}>Output</div>
        </div>
        {err ? (
          <pre style={{ ...preStyle, color: "var(--danger)" }}>{err}</pre>
        ) : (
          <pre style={preStyle}>{resp ? pretty(resp) : "No response yet."}</pre>
        )}
      </div>
    </div>
  );
}

const inputStyle: React.CSSProperties = {
  width: "100%",
  padding: "10px 10px",
  borderRadius: 10,
  border: "1px solid var(--border)",
  background: "var(--panel-2)",
  color: "var(--text)",
  outline: "none",
};

const preStyle: React.CSSProperties = {
  margin: 0,
  padding: 12,
  background: "var(--bg)",
  color: "var(--text)",
  fontFamily: "var(--font-mono)",
  fontSize: 12,
  overflow: "auto",
  minHeight: 120,
};
