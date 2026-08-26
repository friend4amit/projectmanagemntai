const API_BASE = process.env.NODE_ENV === "development" ? "http://localhost:8000" : "";

export const apiFetch = (path: string, init?: RequestInit) =>
  fetch(`${API_BASE}${path}`, { ...init, credentials: "include" });

export const apiSendJson = (path: string, method: string, body: unknown) =>
  apiFetch(path, {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
