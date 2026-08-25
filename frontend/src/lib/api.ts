const API_BASE = process.env.NODE_ENV === "development" ? "http://localhost:8000" : "";

export const apiFetch = (path: string, init?: RequestInit) =>
  fetch(`${API_BASE}${path}`, { ...init, credentials: "include" });
