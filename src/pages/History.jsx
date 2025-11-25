// src/pages/History.jsx
import React from "react";

export default function History({ items }) {
  if (!items || items.length === 0)
    return (
      <div className="panel card bg-panel border-soft shadow-1 p-4">
        No history yet.
      </div>
    );
  return (
    <div className="panel card bg-panel border-soft shadow-1 p-4">
      <div className="history list-group list-group-flush">
        {items.map((it, i) => (
          <div
            key={i}
            className="list-group-item bg-transparent border-0 px-0 text-white"
          >
            <b className="text-uppercase">{it.type}</b> —{" "}
            {new Date(it.at).toLocaleString()}
          </div>
        ))}
      </div>
    </div>
  );
}
