import React, { useEffect, useState } from "react";
import "../styles/layout.css";
import { fetchBootstrap, Bootstrap } from "../api/bootstrap";
import { Sidebar } from "../components/Sidebar";
import { AppRouter } from "./Router";

export function App() {
  const [boot, setBoot] = useState<Bootstrap | null>(null);
  const [err, setErr] = useState<string>("");

  useEffect(() => {
    fetchBootstrap()
      .then(setBoot)
      .catch((e) => setErr(String(e)));
  }, []);

  if (err) return <div style={{ padding: 16 }}>Error: {err}</div>;
  if (!boot) return <div style={{ padding: 16 }}>Loading...</div>;

  return (
    <div className="shell">
      <div className="shell__sidebar">
        <Sidebar menus={boot.menus} />
      </div>

      <div className="shell__main">
        <div className="shell__topbar">
          <div className="topbar__left">
            <div className="brand">AI PaaS</div>
            <div className="badge">tenant: {boot.tenant?.id ?? "unknown"}</div>
          </div>

          <div className="topbar__right">
            <div className="badge">user: {boot.user?.display_name ?? boot.user?.id ?? "unknown"}</div>
            <button className="btn" type="button" onClick={() => alert("TODO: logout")}>
              Logout
            </button>
          </div>
        </div>

        <div className="shell__content">
          <AppRouter />
        </div>
      </div>
    </div>
  );
}