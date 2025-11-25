// src/services/api.js
const API_BASE =
  import.meta?.env?.VITE_BACKEND_URL?.trim() ||
  process.env.REACT_APP_API_BASE?.trim() ||
  "http://127.0.0.1:8000";

async function postFile(path, file, fieldName = "file") {
  const fd = new FormData();
  fd.append(fieldName, file);
  const res = await fetch(`${API_BASE}${path}`, { method: "POST", body: fd });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

async function postJson(path, body) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {}),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

async function getJson(path) {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
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
};
