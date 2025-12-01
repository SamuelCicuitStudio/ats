// src/pages/History.jsx
import React, { useEffect, useState } from "react";
import { api } from "../services/api";

export default function History({ items: provided }) {
  const [items, setItems] = useState(provided || []);
  const [err, setErr] = useState("");

  useEffect(() => {
    if (provided) return;
    let mounted = true;
    api
      .history(100)
      .then((data) => {
        if (mounted && data?.items) setItems(data.items);
      })
      .catch((e) => {
        if (mounted) setErr(String(e));
      });
    return () => {
      mounted = false;
    };
  }, [provided]);

  if (!items || items.length === 0) return <div>No history yet.</div>;

  return (
    <div className="history list-group list-group-flush">
      {err && <div className="alert alert-danger mb-2">{err}</div>}
      {items.map((it) => (
        <div key={it.id} className="list-group-item bg-transparent border-0 px-0">
          <div className="fw-semibold text-uppercase">{it.kind}</div>
          <div className="muted small">{new Date(it.created_at).toLocaleString()}</div>
          {it.payload?.storage?.json_path && (
            <div className="small">
              <a
                href={api.storageFileUrl(it.payload.storage.json_path)}
                target="_blank"
                rel="noreferrer"
              >
                JSON
              </a>
            </div>
          )}
          {it.payload?.storage?.raw_path && (
            <div className="small">
              <a
                href={api.storageFileUrl(it.payload.storage.raw_path)}
                target="_blank"
                rel="noreferrer"
              >
                Original
              </a>
            </div>
          )}
          {it.payload?.storage?.path && (
            <div className="small">
              <a
                href={api.storageFileUrl(it.payload.storage.path)}
                target="_blank"
                rel="noreferrer"
              >
                Download
              </a>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
