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
      <div className="app-shell">
        <header className="topbar">
          <h1>ATS Pipeline</h1>
        </header>
        <main className="content auth-content">
          <div className="content-inner auth-inner">
            <User user={user} onLogin={handleLogin} fullPage />
          </div>
        </main>
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
      </header>

      <div className="layout">
        <aside className="sidebar">
          <TabNav active={tab} onChange={(t) => setTab(t)} items={navItems} />
        </aside>

        <main className="content">
          <div className="content-inner">
            {tab === "pipeline" && (
              <Pipeline onStoreHistory={handleStoreHistory} />
            )}
            {tab === "tests" && <TestGen onStoreHistory={handleStoreHistory} />}
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
