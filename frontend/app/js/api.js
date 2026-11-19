// Talks to the D&T Sketch-to-3D backend (backend/app.py).

const CODE_KEY = "dnt_access_code";

function apiBase() {
  const base = (window.DNT_CONFIG && window.DNT_CONFIG.apiBase) || "";
  return base.replace(/\/+$/, "");
}

export function isSameOrigin() {
  return apiBase() === "";
}

export function url(path) {
  return apiBase() + path;
}

function storedCode() {
  try { return localStorage.getItem(CODE_KEY) || ""; } catch { return ""; }
}

export function rememberCode(code) {
  try { localStorage.setItem(CODE_KEY, code); } catch { /* private mode: cookie still works */ }
}

export class AccessCodeNeeded extends Error {}

export class ApiError extends Error {
  constructor(message, status) { super(message); this.status = status; }
}

async function request(path, options = {}) {
  const headers = new Headers(options.headers || {});
  const code = storedCode();
  if (code) headers.set("X-Access-Code", code);
  let res;
  try {
    res = await fetch(url(path), { ...options, headers, credentials: "include" });
  } catch (e) {
    throw new ApiError("Cannot reach the 3D engine. Is the laptop server still running, and are both devices on the same network?", 0);
  }
  if (res.status === 401) {
    let body = {};
    try { body = await res.json(); } catch { /* ignore */ }
    if (body.code === "access_code_required" || path !== "/auth") throw new AccessCodeNeeded();
    throw new ApiError(body.detail || "Access code not accepted", 401);
  }
  if (!res.ok) {
    let detail = `Error ${res.status}`;
    try { const b = await res.json(); detail = b.detail || detail; } catch { /* ignore */ }
    throw new ApiError(typeof detail === "string" ? detail : JSON.stringify(detail), res.status);
  }
  return res;
}

export async function health() {
  return (await request("/health")).json();
}

export async function login(code) {
  const res = await request("/auth", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ code }),
  });
  rememberCode(code);
  return res.json();
}

export async function convert(blob, filename, base) {
  const fd = new FormData();
  fd.append("file", blob, filename);
  const params = new URLSearchParams({ model: "triposr", base, remove_bg: "true", post: "standard", resolution: "256" });
  return (await request(`/convert?${params}`, { method: "POST", body: fd })).json();
}

export async function status(jobId) {
  return (await request(`/status/${encodeURIComponent(jobId)}`)).json();
}

export async function cancel(jobId) {
  return (await request(`/jobs/${encodeURIComponent(jobId)}/cancel`, { method: "POST" })).json();
}

export async function adjust(jobId, adj) {
  return (await request(`/jobs/${encodeURIComponent(jobId)}/adjust`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      rotate_x: adj.rotate[0], rotate_y: adj.rotate[1], rotate_z: adj.rotate[2],
      size_percent: adj.size, base: adj.base,
    }),
  })).json();
}

export async function fetchArrayBuffer(path) {
  return (await request(path)).arrayBuffer();
}

export async function fetchBlob(path) {
  return (await request(path)).blob();
}
