import React, { useEffect, useMemo, useState } from "react";
import { opaGetPolicy, opaListPolicies, opaUpsertPolicy, OpaPolicy } from "../api/opa";

export function OpaConsole() {
  const [policies, setPolicies] = useState<OpaPolicy[]>([]);
  const [selectedId, setSelectedId] = useState<string>("policy/ui.rego");
  const [raw, setRaw] = useState<string>("");
  const [busy, setBusy] = useState<boolean>(false);
  const [err, setErr] = useState<string>("");

  async function refreshList() {
    const data = await opaListPolicies();
    setPolicies(data);
    // 如果当前选中项不存在了，回退选第一个
    if (data.length && !data.find((p) => p.id === selectedId)) {
      setSelectedId(data[0].id);
    }
  }

  async function loadSelected(id: string) {
    setErr("");
    setBusy(true);
    try {
      const p = await opaGetPolicy(id);
      setRaw(p.raw || "");
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
    <div style={{ display: "flex", height: "100%" }}>
      {/* left */}
      <div style={{ width: 320, borderRight: "1px solid var(--border)", overflow: "auto" }}>
        <div style={{ padding: 12, borderBottom: "1px solid var(--border)", fontWeight: 650 }}>OPA Policies</div>

        {leftItems.map((p) => {
          const active = p.id === selectedId;
          return (
            <button
              key={p.id}
              type="button"
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
              <div style={{ fontSize: 13, fontWeight: 650 }}>{p.id}</div>
              <div style={{ fontSize: 12, color: "var(--muted)", marginTop: 4 }}>
                {(p.raw || "").split("\n").length} lines
              </div>
            </button>
          );
        })}
      </div>

      {/* right */}
      <div style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column" }}>
        <div
          style={{
            padding: 12,
            borderBottom: "1px solid var(--border)",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            gap: 12,
          }}
        >
          <div style={{ fontWeight: 650, minWidth: 0, overflow: "hidden", textOverflow: "ellipsis" }}>
            Raw — {selectedId}
          </div>

          <div style={{ display: "flex", gap: 8 }}>
            <button className="btn" type="button" onClick={() => loadSelected(selectedId)} disabled={busy}>
              Refresh
            </button>
            <button className="btn" type="button" onClick={onSave} disabled={busy}>
              Save
            </button>
          </div>
        </div>

        {err ? (
          <div style={{ padding: 12, color: "var(--danger)" }}>{err}</div>
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
