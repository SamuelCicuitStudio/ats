// src/components/ChatFab.jsx
import React, { useState } from "react";
import { api } from "../services/api.js";

export default function ChatFab() {
  const [open, setOpen] = useState(false);
  const [session, setSession] = useState(null); // {id, pages, bytes}
  const [messages, setMessages] = useState([]); // {role:'user'|'assistant', content}
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  async function uploadPdf(e) {
    const f = e.target.files?.[0];
    if (!f) return;
    setErr("");
    setBusy(true);
    try {
      const meta = await api.kpiLoad(f);
      setSession({ id: meta.session_id, pages: meta.pages, bytes: meta.bytes });
      setMessages([
        {
          role: "assistant",
          content: `PDF loaded (${meta.pages} pages). Ask me about it.`,
        },
      ]);
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function ask() {
    if (!session?.id || !q.trim()) return;
    setErr("");
    setBusy(true);
    try {
      const question = q.trim();
      setMessages((m) => [...m, { role: "user", content: question }]);
      setQ("");
      const data = await api.kpiAsk(session.id, question);
      setMessages((m) => [...m, { role: "assistant", content: data.answer }]);
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <button className="fab" onClick={() => setOpen((o) => !o)}>
        💬
      </button>
      {open && (
        <div className="chat">
          <div className="chat-head">
            <b>KPI Chat</b>
            <label className="upload-btn">
              Upload PDF
              <input
                type="file"
                accept="application/pdf"
                onChange={uploadPdf}
                hidden
              />
            </label>
          </div>

          <div className="chat-body">
            {messages.map((m, i) => (
              <div key={i} className={`msg ${m.role}`}>
                {m.content}
              </div>
            ))}
            {err && <div className="error">{err}</div>}
          </div>

          <div className="chat-foot">
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder={
                session ? "Ask about the report..." : "Upload a PDF first"
              }
              disabled={!session || busy}
            />
            <button onClick={ask} disabled={!session || busy || !q.trim()}>
              Send
            </button>
          </div>
        </div>
      )}
    </>
  );
}
