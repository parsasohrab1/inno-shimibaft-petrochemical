const API_BASE = (import.meta as any).env?.VITE_API_BASE || "http://127.0.0.1:8000";

export class AuthError extends Error {}

let token = "";
export function getToken() {
  return token;
}
export function setToken(t: string) {
  token = t;
}

export type Role = "admin" | "process_engineer" | "energy_engineer" | "quality_engineer";

export async function login(username: string, password: string): Promise<Role> {
  const r = await fetch(`${API_BASE}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  if (!r.ok) throw new AuthError("login failed");
  const body = await r.json();
  setToken(body.access_token);
  return body.user.role as Role;
}

export async function api<T = unknown>(path: string, init: RequestInit = {}): Promise<T> {
  const r = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { ...(init.headers || {}), Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
  });
  if (r.status === 401) throw new AuthError("unauthorized");
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}
