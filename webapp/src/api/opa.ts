// webapp/src/api/opa.ts
// All requests go through Vite proxy: /opa-api -> http://127.0.0.1:8181
// so browser never directly touches :8181 (avoid CORS).

export type OpaPolicy = {
  id: string;
  raw?: string;
};

async function _check(r: Response, msg: string) {
  if (r.ok) return;
  const text = await r.text().catch(() => "");
  throw new Error(`${msg}: ${r.status} ${text}`);
}

export async function opaHealth(): Promise<{ ok: boolean; text: string }> {
  const r = await fetch("/opa-api/health", { method: "GET" });
  const text = await r.text().catch(() => "");
  return { ok: r.status === 200, text };
}

export async function opaListPolicies(): Promise<OpaPolicy[]> {
  const r = await fetch("/opa-api/v1/policies", { method: "GET" });
  await _check(r, "OPA /v1/policies failed");
  const data = (await r.json()) as { result?: Array<{ id: string; raw?: string }> };
  const arr = data.result || [];
  return arr.map((p) => ({ id: p.id, raw: p.raw }));
}

export async function opaGetPolicy(id: string): Promise<string> {
  const r = await fetch(`/opa-api/v1/policies/${encodeURIComponent(id)}`, {
    method: "GET",
  });
  await _check(r, `OPA GET /v1/policies/${id} failed`);
  return await r.text();
}

export async function opaUpsertPolicy(id: string, rego: string): Promise<void> {
  const r = await fetch(`/opa-api/v1/policies/${encodeURIComponent(id)}`, {
    method: "PUT",
    headers: { "Content-Type": "text/plain; charset=utf-8" },
    body: rego,
  });
  await _check(r, `OPA PUT /v1/policies/${id} failed`);
}

export async function opaDeletePolicy(id: string): Promise<void> {
  const r = await fetch(`/opa-api/v1/policies/${encodeURIComponent(id)}`, {
    method: "DELETE",
  });
  await _check(r, `OPA DELETE /v1/policies/${id} failed`);
}

export async function opaEvalUiAllow(input: Record<string, unknown>): Promise<unknown> {
  const r = await fetch("/opa-api/v1/data/ui/allow", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ input }),
  });
  await _check(r, "OPA POST /v1/data/ui/allow failed");
  return await r.json();
}