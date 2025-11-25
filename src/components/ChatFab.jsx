// src/components/ChatFab.jsx
import React, { useEffect, useRef, useState } from "react";
import { api } from "../services/api.js";

export default function ChatFab() {
  const [open, setOpen] = useState(false);
  const [session, setSession] = useState(null);
  const [messages, setMessages] = useState([]);
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
          timestamp: new Date().toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit",
          }),
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
      setMessages((m) => [
        ...m,
        {
          role: "user",
          content: question,
          timestamp: new Date().toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit",
          }),
        },
      ]);
      setQ("");
      const data = await api.kpiAsk(session.id, question);
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          content: data.answer,
          timestamp: new Date().toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit",
          }),
        },
      ]);
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  }

  // Close when clicking outside the chat card/fab
  const cardRef = useRef(null);
  const fabRef = useRef(null);
  useEffect(() => {
    function handleClickOutside(e) {
      if (!open) return;
      const card = cardRef.current;
      const fab = fabRef.current;
      if (
        card &&
        !card.contains(e.target) &&
        fab &&
        !fab.contains(e.target)
      ) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [open]);

  return (
    <>
      <button
        className="fab btn btn-primary rounded-circle position-fixed end-0 bottom-0 m-4"
        onClick={() => setOpen((o) => !o)}
        ref={fabRef}
      >
        💬
      </button>
      {open && (
        <div
          ref={cardRef}
          id="chat2"
          className="chat card position-fixed end-0 bottom-0 me-4 mb-5 border-soft"
        >
          <div className="card-header d-flex justify-content-between align-items-center">
            <h5 className="mb-0">KPI Chat</h5>
            <div className="d-flex align-items-center gap-2">
              <label className="btn btn-sm btn-outline-secondary mb-0">
                Upload PDF
                <input
                  type="file"
                  accept="application/pdf"
                  onChange={uploadPdf}
                  hidden
                />
              </label>
              <button
                type="button"
                className="btn btn-sm btn-outline-secondary"
                onClick={() => setOpen(false)}
              >
                _
              </button>
            </div>
          </div>

          <div className="card-body chat-body">
            {messages.map((m, i) => (
              <div
                key={i}
                className={`chat-row ${
                  m.role === "user" ? "justify-content-end" : "justify-content-start"
                }`}
              >
                {m.role === "assistant" && (
                  <div className="chat-avatar">AI</div>
                )}
                <div className="chat-bubble-wrap">
                  <p className={`chat-bubble ${m.role}`}>{m.content}</p>
                  {m.timestamp && (
                    <p className="chat-time">{m.timestamp}</p>
                  )}
                </div>
                {m.role === "user" && <div className="chat-avatar user">You</div>}
              </div>
            ))}
            {err && <div className="alert alert-danger mt-2">{err}</div>}
          </div>

          <div className="card-footer chat-footer">
            <input
              className="form-control form-control-lg"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder={
                session ? "Type message..." : "Upload a PDF first"
              }
              disabled={!session || busy}
            />
            <button
              className="btn btn-primary btn-lg ms-2"
              onClick={ask}
              disabled={!session || busy || !q.trim()}
            >
              Send
            </button>
          </div>
        </div>
      )}
    </>
  );
}
