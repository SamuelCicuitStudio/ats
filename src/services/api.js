// src/services/api.js
// CRA uses REACT_APP_* env vars; fallback to localhost backend.
const API_BASE =
  process.env.REACT_APP_API_BASE?.trim() || "http://127.0.0.1:8000";

function authHeaders(token) {
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function postFile(path, file, fieldName = "file", token, opts = {}) {
  const { signal } = opts;
  const fd = new FormData();
  fd.append(fieldName, file);
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    body: fd,
    headers: authHeaders(token),
    signal,
  });
  if (!res.ok) {
    const msg = await extractError(res);
    throw new Error(msg);
  }
  return res.json();
}

async function postJson(path, body, token, opts = {}) {
  const { signal } = opts;
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders(token) },
    body: JSON.stringify(body || {}),
    signal,
  });
  if (!res.ok) {
    const msg = await extractError(res);
    throw new Error(msg);
  }
  return res.json();
}

async function patchJson(path, body, token, opts = {}) {
  const { signal } = opts;
  const res = await fetch(`${API_BASE}${path}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", ...authHeaders(token) },
    body: JSON.stringify(body || {}),
    signal,
  });
  if (!res.ok) {
    const msg = await extractError(res);
    throw new Error(msg);
  }
  return res.json();
}

async function getJson(path, token, opts = {}) {
  const { signal } = opts;
  const res = await fetch(`${API_BASE}${path}`, {
    headers: authHeaders(token),
    signal,
  });
  if (!res.ok) {
    const msg = await extractError(res);
    throw new Error(msg);
  }
  return res.json();
}

async function del(path, token, opts = {}) {
  const { signal } = opts;
  const res = await fetch(`${API_BASE}${path}`, {
    method: "DELETE",
    headers: authHeaders(token),
    signal,
  });
  if (!res.ok) {
    const msg = await extractError(res);
    throw new Error(msg);
  }
  return res.json();
}

// Normalize backend error payloads (JSON with .detail) to a readable string.
async function extractError(res) {
  const text = await res.text();
  try {
    const data = JSON.parse(text);
    if (data && typeof data.detail === "string") return data.detail;
  } catch (_) {
    // ignore parse errors; fallback to raw text
  }
  return text || `HTTP ${res.status}`;
}

export const api = {
  base: API_BASE,
  // health
  health: () => getJson("/health"),
  // parsers
  parseCV: (file, opts) => postFile("/cv/parse", file, "file", undefined, opts),
  parseJD: (file, opts) => postFile("/jd/parse", file, "file", undefined, opts),
  // match
  match: (cv, jd, weights, opts) =>
    postJson("/match", { cv, jd, weights }, undefined, opts),
  matchBulk: (cvs, jd, weights, opts) =>
    postJson("/match/bulk", { cvs, jd, weights }, undefined, opts),
  // test gen
  genQuestions: (jd, opts) => postJson("/tests/generate", { jd }, undefined, opts),
  // history & summary
  history: (limit = 50, kind) =>
    getJson(`/history?limit=${encodeURIComponent(limit)}${kind ? `&kind=${encodeURIComponent(kind)}` : ""}`),
  summary: () => getJson("/dashboard/summary"),
  storageFileUrl: (path) => `${API_BASE}/storage/file?path=${encodeURIComponent(path)}`,
  // kpi chat
  kpiLoad: (file) => postFile("/kpi/load", file),
  kpiAsk: (session_id, question) =>
    postJson("/kpi/ask", { session_id, question }),
  // auth & users
  login: (username, password) => postJson("/login", { username, password }),
  listUsers: (token) => getJson("/users", token),
  createUser: (token, payload) => postJson("/users", payload, token),
  updateUser: (token, username, payload) =>
    patchJson(`/users/${encodeURIComponent(username)}`, payload, token),
  deleteUser: (token, username) =>
    del(`/users/${encodeURIComponent(username)}`, token),
  updateSelf: (token, payload) => patchJson("/users/me", payload, token),
};
