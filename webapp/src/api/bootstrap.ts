// webapp/src/api/bootstrap.ts
export type MenuItem = {
  id: string;
  title: string;
  icon?: string;
  route?: string;
  type?: string;
  url?: string;
  capability?: string;
  children?: MenuItem[];
};

export type Bootstrap = {
  user?: { id: string; display_name?: string; is_admin?: boolean };
  tenant?: { id: string; name?: string };
  capabilities?: Record<string, any>;
  menus: MenuItem[];
  layout?: Record<string, any>;
  features?: Record<string, any>;
};

function getToken(): string {
  // ✅ 统一：你在 Console 里 set 的就是 AI_PAAS_TOKEN
  return (localStorage.getItem("AI_PAAS_TOKEN") || "").trim();
}

export async function fetchBootstrap(): Promise<Bootstrap> {
  const token = getToken();
  if (!token) {
    throw new Error("Missing token: localStorage.AI_PAAS_TOKEN is empty");
  }

  // ✅ 走相对路径，让 Vite proxy / 未来 Nginx 反代接管
  const r = await fetch("/api/v1/ui/bootstrap", {
    method: "GET",
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  if (!r.ok) {
    const text = await r.text().catch(() => "");
    throw new Error(`bootstrap failed: ${r.status} ${text}`);
  }

  return (await r.json()) as Bootstrap;
}
