import React, { useRef } from "react";

export default function TabNav({ active, onChange, items = [], tabs }) {
  const list = tabs ?? items ?? [];
  const refs = useRef({});

  function onKeyDown(e, idx) {
    if (!["ArrowDown", "ArrowUp"].includes(e.key)) return;
    e.preventDefault();
    const next = e.key === "ArrowDown" ? idx + 1 : idx - 1;
    const clamped = (next + list.length) % list.length;
    const nextId = list[clamped]?.id ?? list[clamped]?.key;
    refs.current[nextId]?.focus();
  }

  return (
    <nav className="tabnav w-100">
      <ul className="nav nav-tabs flex-column tabs-left w-100">
        {list.map((t, i) => {
          const id = t.id ?? t.key;
          const isActive = active === id;
          return (
            <li className="nav-item w-100" key={id}>
              <button
                ref={(el) => (refs.current[id] = el)}
                className={`nav-link d-flex align-items-center justify-content-between w-100 ${
                  isActive ? "active" : ""
                }`}
                onClick={() => onChange?.(id)}
                onKeyDown={(e) => onKeyDown(e, i)}
                role="tab"
                aria-selected={isActive}
                title={t.title || t.label || id}
                type="button"
              >
                <span className="d-flex align-items-center gap-2">
                  {t.icon && <span aria-hidden>{t.icon}</span>}
                  <span>{t.label ?? t.name ?? id}</span>
                </span>
                {typeof t.count === "number" && (
                  <span className="badge bg-secondary-subtle text-body-secondary">
                    {t.count}
                  </span>
                )}
              </button>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
