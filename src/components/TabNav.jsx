// src/components/TabNav.jsx
import React from "react";

// Accepts either `items` (preferred) or `tabs` for compatibility.
export default function TabNav({ active, onChange, items = [], tabs }) {
  const list = tabs ?? items ?? [];

  return (
    <nav className="tabnav">
      {list.map((t) => {
        const id = t.id ?? t.key;
        return (
          <button
            key={id}
            className={`tabbtn ${active === id ? "active" : ""}`}
            onClick={() => onChange?.(id)}
          >
            {t.label ?? t.name ?? id}
          </button>
        );
      })}
    </nav>
  );
}
