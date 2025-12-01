// src/App.js
import React, { useRef, useState } from "react";
import ChatFab from "./components/ChatFab";
import JobBar from "./components/JobBar";

import Pipeline from "./pages/Pipeline";
import TestGen from "./pages/TestGen";
import History from "./pages/History";
import User from "./pages/User";
import Users from "./pages/Users";
import Home from "./pages/Home";

import "./index.css";
import "./App.css";

const StreamingPlaceholder = () => (
  <section className="canvas">
    <div className="header">
      <h2>Streaming CV</h2>
    </div>
    <div className="paper-wrap">
      <div className="paper">
        <div className="tile">
          <svg
            className="giant"
            viewBox="0 0 24 24"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
            stroke="var(--primary)"
            strokeWidth="1.6"
          >
            <rect x="6" y="4" width="12" height="16" rx="2" stroke="var(--primary)" />
            <path d="M9 8h6M9 12h6M9 16h4" stroke="var(--primary)" />
          </svg>
          <h4 style={{ color: "#0f172a" }}>Fonctionnalite en developpement</h4>
          <p className="muted">Le streaming de CV sera bientot disponible</p>
        </div>
      </div>
    </div>
    <div className="footer">(c) 2025 ATS Platform. Tous droits reserves.</div>
  </section>
);

const HistoriquePlaceholder = ({ items }) => (
  <section className="canvas">
    <div className="header">
      <h2>Historique</h2>
    </div>
    <div className="section">
      <History items={items} />
    </div>
    <div className="footer">(c) 2025 ATS Platform. Tous droits reserves.</div>
  </section>
);

export default function App() {
  const [tab, setTab] = useState("home");
  const [history, setHistory] = useState([]);
  const [session, setSession] = useState(null);
  const [job, setJob] = useState(null);
  const jobController = useRef(null);

  const user = session?.user;

  const handleStoreHistory = (entry) => {
    setHistory((prev) => [entry, ...prev].slice(0, 200));
  };

  const handleLogin = (loginResp) => {
    setSession(loginResp);
  };

  const handleUserUpdate = (updated) => {
    setSession((prev) =>
      prev ? { ...prev, user: { ...prev.user, ...updated } } : prev
    );
  };

  const startJob = (payload) => {
    const controller = new AbortController();
    jobController.current = controller;
    setJob({
      status: "running",
      progress: { done: 0, total: 0, message: "" },
      ...payload,
    });
    return controller;
  };

  const updateJob = (patch) => {
    setJob((prev) => (prev ? { ...prev, ...patch } : prev));
  };

  const clearJob = () => {
    jobController.current = null;
    setJob(null);
  };

  const cancelJob = () => {
    setJob((prev) =>
      prev ? { ...prev, status: "cancelling", detail: prev.detail || "Annulation..." } : prev
    );
    if (jobController.current) jobController.current.abort();
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
    { key: "home", label: "Accueil" },
    { key: "pipeline", label: "Pipeline de Recrutement" },
    { key: "tests", label: "Generation de Tests" },
    { key: "streaming", label: "Streaming CV" },
    { key: "historique", label: "Historique" },
    { key: "users", label: "Gestion utilisateur", admin: true },
  ];

  const jobActive = !!job && job.status !== "done";

  const screens = [
    { key: "home", element: <Home /> },
    {
      key: "pipeline",
      element: (
        <Pipeline
          onStoreHistory={handleStoreHistory}
          job={job}
          jobActive={jobActive}
          onJobStart={startJob}
          onJobUpdate={updateJob}
          onJobClear={clearJob}
          onJobCancel={cancelJob}
        />
      ),
    },
    {
      key: "tests",
      element: (
        <TestGen
          onStoreHistory={handleStoreHistory}
          job={job}
          jobActive={jobActive}
          onJobStart={startJob}
          onJobUpdate={updateJob}
          onJobClear={clearJob}
          onJobCancel={cancelJob}
        />
      ),
    },
    {
      key: "users",
      element: (
        <section className="canvas">
          <div className="header">
            <h2>Gestion utilisateur</h2>
          </div>
          <div className="section">
            <Users session={session} onUserUpdate={handleUserUpdate} />
          </div>
          <div className="footer">(c) 2025 ATS Platform. Tous droits reserves.</div>
        </section>
      ),
    },
    { key: "streaming", element: <StreamingPlaceholder /> },
    { key: "historique", element: <HistoriquePlaceholder items={history} /> },
  ];

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="dot" aria-hidden="true"></div>
          <h1>ATS Platform</h1>
        </div>
        <nav className="nav" id="side-nav">
          {navItems.map((item) => (
            <a
              key={item.key}
              href="#"
              data-screen={item.key}
              className={`${tab === item.key ? "active" : ""} ${
                item.admin ? "nav-admin" : ""
              }`}
              onClick={(e) => {
                e.preventDefault();
                setTab(item.key);
              }}
            >
              <span className="bar" aria-hidden="true"></span>
              {item.label}
            </a>
          ))}
        </nav>
      </aside>

      <header className="topbar">
        <div className="title">ATS Platform</div>
        <div className="actions">
          <a
            href="#"
            onClick={(e) => {
              e.preventDefault();
              setTab("users");
            }}
          >
            Profil
          </a>
          <a
            href="#"
            onClick={(e) => {
              e.preventDefault();
              clearJob();
              setSession(null);
            }}
          >
            Deconnexion
          </a>
        </div>
      </header>

      <main className="content">
        {screens.map((screen) => {
          const isActive = tab === screen.key;
          const hidden = !isActive;
          return (
            <div
              key={screen.key}
              style={{ display: hidden ? "none" : "block" }}
              aria-hidden={hidden}
              data-screen-panel={screen.key}
            >
              {screen.element}
            </div>
          );
        })}
      </main>

      <JobBar job={jobActive ? job : null} onCancel={cancelJob} />
      <ChatFab />
    </div>
  );
}
