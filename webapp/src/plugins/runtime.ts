export type PluginHandshakeV1 = {
  type: "aios.plugin.handshake";
  v: 1;
  plugin_id?: string;
  request_id: string;
};

export type PluginContextV1 = {
  type: "aios.host.context";
  v: 1;
  request_id: string;

  // identity / tenancy
  user: { id: string; display_name?: string; is_admin?: boolean };
  tenant: { id: string };

  // short-lived token for plugin -> gateway calls (or plugin backend)
  token?: string;

  // ui tokens
  theme: { mode: "dark" | "light"; tokens: Record<string, string> };
  locale?: string;

  // tracing
  trace_id: string;
};

export type PluginEventV1 =
  | PluginHandshakeV1
  | PluginContextV1
  | { type: "aios.plugin.telemetry"; v: 1; trace_id: string; level: "info" | "warn" | "error"; message: string; data?: any }
  | { type: "aios.plugin.request"; v: 1; trace_id: string; request_id: string; op: string; payload?: any }
  | { type: "aios.host.response"; v: 1; trace_id: string; request_id: string; ok: boolean; payload?: any; error?: string };

export function randomId(prefix = "r"): string {
  return `${prefix}_${Math.random().toString(16).slice(2)}_${Date.now().toString(16)}`;
}

/**
 * Conservative origin check:
 * - allow same-origin
 * - allow explicit allowedOrigins entries
 */
export function isAllowedOrigin(origin: string, allowedOrigins: string[]): boolean {
  if (!origin) return false;
  const same = origin === window.location.origin;
  if (same) return true;
  return allowedOrigins.includes(origin);
}

/**
 * Wait for iframe plugin handshake, then send context.
 * Returns a disposer that removes event listener.
 */
export function bindPluginHandshake(opts: {
  iframeEl: HTMLIFrameElement;
  pluginId: string;
  allowedOrigins: string[]; // plugin origin allowlist (can include same-origin implicitly)
  buildContext: (requestId: string) => PluginContextV1;
  timeoutMs?: number;
  onLog?: (msg: string) => void;
}): { dispose: () => void; ready: Promise<void> } {
  const { iframeEl, pluginId, allowedOrigins, buildContext, timeoutMs = 5000, onLog } = opts;

  let resolved = false;
  let timer: any = null;

  const ready = new Promise<void>((resolve, reject) => {
    timer = setTimeout(() => {
      if (!resolved) {
        reject(new Error(`Plugin handshake timeout (${timeoutMs}ms): ${pluginId}`));
      }
    }, timeoutMs);

    function onMessage(ev: MessageEvent) {
      const data = ev.data as any;
      if (!data || typeof data !== "object") return;
      if (data.type !== "aios.plugin.handshake" || data.v !== 1) return;

      // origin control
      if (!isAllowedOrigin(ev.origin, allowedOrigins)) {
        onLog?.(`Blocked plugin message from origin=${ev.origin} plugin=${pluginId}`);
        return;
      }

      const hs = data as PluginHandshakeV1;
      const requestId = hs.request_id || randomId("hs");

      // send context to the plugin (back to its origin)
      const ctx = buildContext(requestId);
      iframeEl.contentWindow?.postMessage(ctx, ev.origin);

      resolved = true;
      clearTimeout(timer);
      window.removeEventListener("message", onMessage);
      resolve();
    }

    window.addEventListener("message", onMessage);
  });

  return {
    ready,
    dispose: () => {
      clearTimeout(timer);
      window.removeEventListener("message", () => {});
    },
  };
}
