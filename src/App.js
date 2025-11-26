// src/App.js
import React, { useState } from "react";
import TabNav from "./components/TabNav";
import ChatFab from "./components/ChatFab";

import Pipeline from "./pages/Pipeline";
import TestGen from "./pages/TestGen";
import History from "./pages/History";
import User from "./pages/User";
import Users from "./pages/Users";

import "./index.css";
import "./App.css";

export default function App() {
  const [tab, setTab] = useState("pipeline"); // 'pipeline' | 'tests' | 'history' | 'users'
  const [history, setHistory] = useState([]);
  const [session, setSession] = useState(null); // {token, user}

  const user = session?.user;
  const isAdmin = !!(user?.roles || []).includes("admin");

  const handleStoreHistory = (entry) => {
    // entry shape is provided by children (Pipeline/TestGen)
    setHistory((prev) => [entry, ...prev].slice(0, 200));
  };

  const handleLogin = (loginResp) => {
    // loginResp: {token, user}
    setSession(loginResp);
  };

  const handleUserUpdate = (updated) => {
    // updated: partial or full user object
    setSession((prev) =>
      prev ? { ...prev, user: { ...prev.user, ...updated } } : prev
    );
  };

  if (!session) {
    return (
      <div className="auth-wrapper">
        <div id="formContent" className="auth-card fadeInDown">
          <User user={user} onLogin={handleLogin} fullPage />
        </div>
      </div>
    );
  }

  const navItems = [
    { key: "pipeline", label: "Pipeline" },
    { key: "tests", label: "Test Generation" },
    { key: "history", label: "History" },
    { key: "users", label: "Users" },
  ];

  return (
    <div className="app-shell">
      <header className="topbar">
        <svg
          className="topbar-icon"
          viewBox="0 0 64 40"
          role="img"
          aria-label="ATS visual icon"
        >
          <rect x="2" y="6" width="22" height="28" rx="4" fill="var(--panel)" stroke="var(--accent)" strokeWidth="2" />
          <rect x="40" y="6" width="22" height="28" rx="4" fill="var(--panel)" stroke="var(--accent-strong)" strokeWidth="2" />
          <path
            d="M32 8c7.18 0 13 5.82 13 13s-5.82 13-13 13-13-5.82-13-13 5.82-13 13-13zm0 6.5a6.5 6.5 0 100 13 6.5 6.5 0 000-13zm0-4l1.2 2.8 3-.4-1.8 2.4 1.8 2.4-3-.4-1.2 2.8-1.2-2.8-3 .4 1.8-2.4-1.8-2.4 3 .4 1.2-2.8z"
            fill="url(#topbarGearGrad)"
          />
          <defs>
            <linearGradient id="topbarGearGrad" x1="19" y1="8" x2="45" y2="34" gradientUnits="userSpaceOnUse">
              <stop stopColor="var(--accent)" />
              <stop offset="1" stopColor="var(--accent-strong)" />
            </linearGradient>
          </defs>
        </svg>
        <div className="user-menu">
          <button
            className="user-badge"
            title="Open menu"
            type="button"
          >
            <span className="user-circle">
              {(user.display_name || user.username || "?").charAt(0).toUpperCase()}
            </span>
            <div className="user-meta">
              <div className="user-name">{user.display_name || user.username}</div>
              <div className="user-role">{(user.roles || []).join(", ")}</div>
            </div>
          </button>
          <div className="user-menu-dropdown">
            <button
              type="button"
              className="dropdown-item"
              onClick={() => setSession(null)}
            >
              Disconnect
            </button>
          </div>
        </div>
      </header>

      <div className="layout container-xl py-4 d-flex flex-column flex-lg-row gap-4 align-items-start justify-content-center">
        <aside className="sidebar">
          <TabNav active={tab} onChange={(t) => setTab(t)} items={navItems} />
        </aside>

        <main className="content flex-grow-1 d-flex justify-content-center">
          <div className="content-inner w-100">
            {tab === "pipeline" && (
              <Pipeline onStoreHistory={handleStoreHistory} />
            )}
            {tab === "tests" && (
              <TestGen onStoreHistory={handleStoreHistory} />
            )}
            {tab === "history" && <History items={history} />}
            {tab === "users" && (
              <Users session={session} onUserUpdate={handleUserUpdate} />
            )}
          </div>
        </main>
      </div>

      <ChatFab />
    </div>
  );
}
