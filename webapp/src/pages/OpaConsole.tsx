import React, { useEffect, useMemo, useState } from "react";
import { opaGetPolicy, opaListPolicies, opaUpsertPolicy, OpaPolicy } from "../api/opa";

export function OpaConsole() {
  const [policies, setPolicies] = useState<OpaPolicy[]>([]);
  const [selectedId, setSelectedId] = useState("policy/ui.rego");
  const [raw, setRaw] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  async function refreshList() {
    const data = await opaListPolicies();
    setPolicies(data);

    if (data.length && !data.find((p) => p.id === selectedId)) {
      setSelectedId(data[0].id);
    }
  }

  async function loadSelected(id: string) {
    setErr("");
    setBusy(true);
    try {
      const text = await opaGetPolicy(id);
      setRaw(text || "");
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    refreshList().catch((e) => setErr(String(e)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!selectedId) return;
    loadSelected(selectedId).catch((e) => setErr(String(e)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedId]);

  const leftItems = useMemo(() => policies, [policies]);

  async function onSave() {
    setErr("");
    setBusy(true);
    try {
      await opaUpsertPolicy(selectedId, raw);
      await refreshList();
      await loadSelected(selectedId);
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div
      style={{
        height: "calc(100vh - 120px)",
        display: "grid",
        gridTemplateColumns: "320px 1fr",
        gap: 16,
      }}
    >
      <div
        style={{
          border: "1px solid var(--border)",
          borderRadius: 12,
          overflow: "hidden",
          background: "var(--panel)",
        }}
      >
        <div
          style={{
            padding: "12px 14px",
            borderBottom: "1px solid var(--border)",
            fontWeight: 700,
          }}
        >
          OPA Policies
        </div>

        <div style={{ overflow: "auto", maxHeight: "100%" }}>
          {leftItems.map((p) => {
            const active = p.id === selectedId;
            return (
              <button
                key={p.id}
                onClick={() => setSelectedId(p.id)}
                style={{
                  width: "100%",
                  textAlign: "left",
                  padding: "10px 12px",
                  border: "0",
                  borderBottom: "1px solid var(--border)",
                  background: active ? "rgba(110,168,255,0.12)" : "transparent",
                  color: "var(--text)",
                  cursor: "pointer",
                }}
              >
                <div style={{ fontWeight: 600 }}>{p.id}</div>
                <div style={{ fontSize: 12, color: "var(--muted)" }}>
                  {((p.raw || "").split("\n").length || 0)} lines
                </div>
              </button>
            );
          })}
        </div>
      </div>

      <div
        style={{
          border: "1px solid var(--border)",
          borderRadius: 12,
          background: "var(--panel)",
          display: "flex",
          flexDirection: "column",
          minHeight: 0,
        }}
      >
        <div
          style={{
            padding: "12px 14px",
            borderBottom: "1px solid var(--border)",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: 12,
          }}
        >
          <div style={{ fontWeight: 700 }}>Raw — {selectedId}</div>

          <div style={{ display: "flex", gap: 8 }}>
            <button className="btn" onClick={() => loadSelected(selectedId)} disabled={busy}>
              Refresh
            </button>
            <button className="btn btn-primary" onClick={onSave} disabled={busy}>
              Save
            </button>
          </div>
        </div>

        {err ? (
          <div style={{ padding: "10px 14px", color: "#ff8f8f" }}>
            {err}
          </div>
        ) : null}

        <textarea
          value={raw}
          onChange={(e) => setRaw(e.target.value)}
          spellCheck={false}
          style={{
            flex: 1,
            minHeight: 0,
            width: "100%",
            border: "0",
            outline: "none",
            padding: 12,
            fontFamily: "var(--font-mono)",
            fontSize: 12,
            lineHeight: 1.5,
            color: "var(--text)",
            background: "transparent",
          }}
        />
      </div>
    </div>
  );
}