import React, { useEffect, useMemo, useRef, useState } from "react";
import { useLocation, useParams } from "react-router-dom";

function findMenuById(menus: any[], id: string): any | null {
  for (const m of (menus || [])) {
    if (m?.id === id) return m;
    const child = findMenuById(m?.children || [], id);
    if (child) return child;
  }
  return null;
}

import { fetchBootstrap, Bootstrap } from "../api/bootstrap";

type HostMessage =
  | { type: "AIOS_HOST_CONTEXT"; payload: any }
  | { type: "AIOS_HOST_PING"; ts: number };

type PluginMessage =
  | { type: "AIOS_PLUGIN_READY"; pluginId?: string }
  | { type: "AIOS_PLUGIN_RESIZE"; height: number }
  | { type: "AIOS_PLUGIN_NAVIGATE"; path: string };

export const PluginPage: React.FC = () => {
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const { pluginId } = useParams();
  const loc = useLocation();

  const [bs, setBs] = useState<Bootstrap | null>(null);
  const [err, setErr] = useState<string>("");

  // Load bootstrap on demand (no placeholder, no global store requirement)
  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const b = await fetchBootstrap();
        if (!alive) return;
        setBs(b);
      } catch (e: any) {
        if (!alive) return;
        setErr(e?.message || String(e));
      }
    })();
    return () => {
      alive = false;
    };
  }, []);

  const plugin: any = useMemo(() => {
    if (!bs || !pluginId) return null;
    return findMenuById((bs.menus || []) as any[], pluginId as string);}, [bs, pluginId]);

  function postContext() {
    const iframe = iframeRef.current;
    if (!iframe?.contentWindow || !bs) return;

    const payload = {
      v: 1,
      // NOTE: Your bootstrap may or may not include token. If token is not returned,
      // plugin should rely on cookies / gateway auth or you can extend bootstrap later.
      token: (bs as any).token || "",
      user: bs.user,
      tenant: bs.tenant,
      gatewayBase: "/api",
      pluginId,
      hostPath: loc.pathname + loc.search,
    };

    const msg: HostMessage = { type: "AIOS_HOST_CONTEXT", payload };
    iframe.contentWindow.postMessage(msg, "*");
  }

  useEffect(() => {
    function onMessage(ev: MessageEvent) {
      const msg = ev.data as PluginMessage;
      if (!msg || typeof msg !== "object") return;

      if (msg.type === "AIOS_PLUGIN_READY") {
        postContext();
      }

      if (msg.type === "AIOS_PLUGIN_RESIZE") {
        const h = Math.max(300, Math.min(msg.height, 5000));
        if (iframeRef.current) iframeRef.current.style.height = `${h}px`;
      }
    }

    window.addEventListener("message", onMessage);
    return () => window.removeEventListener("message", onMessage);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pluginId, bs]);

  if (!pluginId) return <div style={{ padding: 16 }}>Missing pluginId</div>;
  if (err) return <div style={{ padding: 16 }}>Bootstrap error: {err}</div>;
  if (!bs) return <div style={{ padding: 16 }}>Loading...</div>;

  if (!plugin) return <div style={{ padding: 16 }}>Plugin not found: {pluginId}</div>;
  if (plugin.type !== "iframe") return <div style={{ padding: 16 }}>Not an iframe plugin: {pluginId}</div>;

  return (
    <div style={{ height: "100%", width: "100%" }}>
      <iframe
        ref={iframeRef}
        title={plugin.title || pluginId}
        src={plugin.iframe_url || plugin.url}
        style={{ width: "100%", height: "80vh", border: "none" }}
        onLoad={() => setTimeout(postContext, 200)}
      />
    </div>
  );
};
