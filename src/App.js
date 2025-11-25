// src/App.js
import React, { useState } from "react";
import TabNav from "./components/TabNav";
import ChatFab from "./components/ChatFab";

import Pipeline from "./pages/Pipeline";
import TestGen from "./pages/TestGen";
import History from "./pages/History";

import "./index.css"; // keep your styles

export default function App() {
  const [tab, setTab] = useState("pipeline"); // 'pipeline' | 'tests' | 'history'
  const [history, setHistory] = useState([]);

  const handleStoreHistory = (entry) => {
    // entry shape is provided by children (Pipeline/TestGen)
    setHistory((prev) => [entry, ...prev].slice(0, 200));
  };

  return (
    <div className="app-shell">
      <header className="topbar">
        <h1>ATS Pipeline</h1>
      </header>

      <TabNav
        active={tab}
        onChange={(t) => setTab(t)}
        items={[
          { key: "pipeline", label: "Pipeline" },
          { key: "tests", label: "Test Generation" },
          { key: "history", label: "History" },
        ]}
      />

      <main className="content">
        {tab === "pipeline" && <Pipeline onStoreHistory={handleStoreHistory} />}
        {tab === "tests" && <TestGen onStoreHistory={handleStoreHistory} />}
        {tab === "history" && <History items={history} />}
      </main>

      <ChatFab />
    </div>
  );
}
