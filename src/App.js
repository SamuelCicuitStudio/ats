// src/App.js
import React, { useEffect, useState } from "react";
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
  const [theme, setTheme] = useState(() => localStorage.getItem("theme") || "light"); // light | dark

  const user = session?.user;
  const isAdmin = !!(user?.roles || []).includes("admin");

  // apply/persist theme
  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("theme", theme);
  }, [theme]);

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
        <h1>ATS Pipeline</h1>
        <div className="d-flex align-items-center gap-2">
          <button
            type="button"
            className="btn btn-outline-primary btn-sm theme-toggle"
            onClick={() => setTheme((t) => (t === "light" ? "dark" : "light"))}
            aria-label="Toggle theme"
          >
            {theme === "light" ? "☀️" : "🌙"}
          </button>
          <button
            className="user-badge"
            title="Click to logout"
            onClick={() => setSession(null)}
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
