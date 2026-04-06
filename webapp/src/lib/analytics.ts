export type UiTrackEvent = {
  id: string;
  ts: string;
  type: string;
  page: string;
  tenant_id?: string;
  user_id?: string;
  payload: Record<string, unknown>;
};

const STORAGE_KEY = "AI_PAAS_UI_EVENTS";
const SESSION_KEY = "AI_PAAS_UI_SESSION_ID";
const MAX_EVENTS = 500;

function nowIso(): string {
  return new Date().toISOString();
}

function randomId(prefix: string): string {
  return `${prefix}_${Math.random().toString(36).slice(2, 10)}_${Date.now()}`;
}

export function getSessionId(): string {
  const existing = localStorage.getItem(SESSION_KEY);
  if (existing) return existing;

  const created = randomId("sess");
  localStorage.setItem(SESSION_KEY, created);
  return created;
}

function loadEvents(): UiTrackEvent[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? (parsed as UiTrackEvent[]) : [];
  } catch {
    return [];
  }
}

function saveEvents(events: UiTrackEvent[]) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(events.slice(-MAX_EVENTS)));
}

export function trackUiEvent(
  type: string,
  page: string,
  payload: Record<string, unknown> = {},
) {
  const event: UiTrackEvent = {
    id: randomId("evt"),
    ts: nowIso(),
    type,
    page,
    tenant_id: (payload.tenant_id as string | undefined) || undefined,
    user_id: (payload.user_id as string | undefined) || undefined,
    payload: {
      session_id: getSessionId(),
      ...payload,
    },
  };

  const next = loadEvents();
  next.push(event);
  saveEvents(next);

  window.dispatchEvent(
    new CustomEvent("ai-paas:track", {
      detail: event,
    }),
  );

  if (import.meta.env.DEV) {
    console.debug("[track]", event);
  }
}

export function getTrackedEvents(): UiTrackEvent[] {
  return loadEvents();
}

export function clearTrackedEvents() {
  localStorage.removeItem(STORAGE_KEY);
}