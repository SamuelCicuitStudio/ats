// src/pages/History.jsx
import React from "react";

export default function History({ items }) {
  if (!items || items.length === 0)
    return <div className="panel">No history yet.</div>;
  return (
    <div className="panel">
      <ul className="history">
        {items.map((it, i) => (
          <li key={i}>
            <b>{it.type}</b> — {new Date(it.at).toLocaleString()}
          </li>
        ))}
      </ul>
    </div>
  );
}
