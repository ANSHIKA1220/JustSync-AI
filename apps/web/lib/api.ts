export const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

export type User = { id: string; email: string; name: string; role: "administrator" | "agent" | "customer" };
export type Workspace = { id: string; organization_id: string; name: string; slug: string; is_default: boolean };
export type Organization = { id: string; name: string; slug: string; plan: string; status: string; workspaces: Workspace[] };
export type HealthStatus = {
  status: string;
  configured_provider: "mock" | "ollama" | "openai" | "gemini" | string;
  active_provider: "mock" | "ollama" | "openai" | "gemini" | string;
  fallback_active: boolean;
  model: string;
  ollama_available: boolean;
  database_mode: string;
};

export function getToken() {
  if (typeof window === "undefined") return "";
  return localStorage.getItem("journeysync_token") || "";
}

export function getUser(): User | null {
  if (typeof window === "undefined") return null;
  const raw = localStorage.getItem("journeysync_user");
  return raw ? JSON.parse(raw) as User : null;
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("Content-Type", "application/json");
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const res = await fetch(`${API_URL}${path}`, { ...init, headers, cache: "no-store" });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(detail || `Request failed: ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export async function login(email: string, password: string) {
  const res = await api<{ access_token: string; user: User }>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password })
  });
  localStorage.setItem("journeysync_token", res.access_token);
  localStorage.setItem("journeysync_user", JSON.stringify(res.user));
  return res;
}

export async function signup(organizationName: string, name: string, email: string, password: string) {
  const res = await api<{ access_token: string; user: User; organization: Organization }>("/auth/signup", {
    method: "POST",
    body: JSON.stringify({ organization_name: organizationName, name, email, password })
  });
  localStorage.setItem("journeysync_token", res.access_token);
  localStorage.setItem("journeysync_user", JSON.stringify(res.user));
  return res;
}

export function getOrganization() {
  return api<Organization>("/organization");
}
