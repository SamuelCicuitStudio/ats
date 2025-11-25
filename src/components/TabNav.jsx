// src/components/TabNav.jsx
import React from "react";

export default function TabNav({ active, onChange, tabs }) {
  return (
    <nav className="tabnav">
      {tabs.map((t) => (
        <button
          key={t.id}
          className={`tabbtn ${active === t.id ? "active" : ""}`}
          onClick={() => onChange(t.id)}
        >
          {t.label}
        </button>
      ))}
    </nav>
  );
}
