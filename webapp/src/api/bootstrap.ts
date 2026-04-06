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
  capabilities?: Record<string, unknown>;
  menus: MenuItem[];
  layout?: Record<string, unknown>;
  features?: Record<string, unknown>;
};

export function getApiToken(): string {
  return (localStorage.getItem("AI_PAAS_TOKEN") || "").trim();
}

export function getApiHeaders(): HeadersInit {
  const token = getApiToken();
  if (!token) {
    throw new Error("Missing token: localStorage.AI_PAAS_TOKEN is empty");
  }
  return {
    Authorization: `Bearer ${token}`,
  };
}

export async function fetchBootstrap(): Promise<Bootstrap> {
  const response = await fetch("/api/ui/bootstrap", {
    method: "GET",
    headers: getApiHeaders(),
  });

  if (!response.ok) {
    const text = await response.text().catch(() => "");
    throw new Error(`bootstrap failed: ${response.status} ${text}`);
  }

  return (await response.json()) as Bootstrap;
}