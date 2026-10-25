const API_BASE = (import.meta.env.VITE_API_BASE_URL || "/api/v1").replace(/\/$/, "");
const TOKEN_KEY = "spms.token";

export class ApiError extends Error {
  constructor(message, { status = 0, code = "error", details = null } = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token) {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

function buildQuery(query) {
  const params = new URLSearchParams();
  Object.entries(query || {}).forEach(([key, value]) => {
    if (value === undefined || value === null || value === "") return;
    if (Array.isArray(value)) value.forEach((item) => params.append(key, item));
    else params.set(key, String(value));
  });
  const encoded = params.toString();
  return encoded ? `?${encoded}` : "";
}

async function parseError(response) {
  let payload = null;
  try {
    payload = await response.json();
  } catch {
    // Non-JSON error body.
  }
  const message =
    payload?.message ||
    payload?.detail?.message ||
    (typeof payload?.detail === "string" ? payload.detail : null) ||
    `Request failed (${response.status})`;
  return new ApiError(message, {
    status: response.status,
    code: payload?.code || "http_error",
    details: payload?.details || payload?.detail || null,
  });
}

export async function api(path, { method = "GET", body, query, token, raw = false } = {}) {
  const headers = {};
  const authToken = token ?? getToken();
  if (authToken) headers.Authorization = `Bearer ${authToken}`;
  let payload;
  if (body instanceof FormData) {
    payload = body;
  } else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }

  let response;
  try {
    response = await fetch(`${API_BASE}${path}${buildQuery(query)}`, {
      method,
      headers,
      body: payload,
    });
  } catch (error) {
    throw new ApiError(
      "Cannot reach the API. Is the backend running on port 8080?",
      { code: "network_error" }
    );
  }

  if (response.status === 401) {
    setToken(null);
  }
  if (!response.ok) throw await parseError(response);
  if (raw) return response;
  if (response.status === 204) return null;
  const text = await response.text();
  return text ? JSON.parse(text) : null;
}

export async function download(path, query, filename) {
  const response = await api(path, { raw: true, query });
  const blob = await response.blob();
  const disposition = response.headers.get("content-disposition") || "";
  const match = disposition.match(/filename="?([^";]+)"?/);
  const name = match?.[1] || filename || "report";
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = name;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}
