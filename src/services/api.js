// src/services/api.js
// CRA uses REACT_APP_* env vars; fallback to localhost backend.
const API_BASE =
  process.env.REACT_APP_API_BASE?.trim() || "http://127.0.0.1:8000";

function authHeaders(token) {
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function postFile(path, file, fieldName = "file", token) {
  const fd = new FormData();
  fd.append(fieldName, file);
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    body: fd,
    headers: authHeaders(token),
  });
  if (!res.ok) {
    const msg = await extractError(res);
    throw new Error(msg);
  }
  return res.json();
}

async function postJson(path, body, token) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders(token) },
    body: JSON.stringify(body || {}),
  });
  if (!res.ok) {
    const msg = await extractError(res);
    throw new Error(msg);
  }
  return res.json();
}

async function patchJson(path, body, token) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", ...authHeaders(token) },
    body: JSON.stringify(body || {}),
  });
  if (!res.ok) {
    const msg = await extractError(res);
    throw new Error(msg);
  }
  return res.json();
}

async function getJson(path, token) {
  const res = await fetch(`${API_BASE}${path}`, { headers: authHeaders(token) });
  if (!res.ok) {
    const msg = await extractError(res);
    throw new Error(msg);
  }
  return res.json();
}

async function del(path, token) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "DELETE",
    headers: authHeaders(token),
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
  parseCV: (file) => postFile("/cv/parse", file),
  parseJD: (file) => postFile("/jd/parse", file),
  // match
  match: (cv, jd, weights) => postJson("/match", { cv, jd, weights }),
  // test gen
  genQuestions: (jd) => postJson("/tests/generate", { jd }),
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
