// src/pages/Home.jsx
import React, { useEffect, useMemo, useState } from "react";
import { api } from "../services/api";

const candidates = [
  {
    name: "Alex Johnson",
    role: "UI Frontend Developer",
    status: "interview",
    email: "alex.johnson@example.com",
    phone: "+1 (555) 123-4567",
    location: "New York, USA",
    applied: "May 10, 2023",
    initials: "A",
  },
  {
    name: "Sarah Williams",
    role: "UI/UX Designer",
    status: "screening",
    email: "sarah.w@example.com",
    phone: "+1 (555) 867-6543",
    location: "San Francisco, USA",
    applied: "May 15, 2023",
    initials: "S",
  },
  {
    name: "Michael Chen",
    role: "Backend Developer",
    status: "new",
    email: "m.chen@example.com",
    phone: "+1 (555) 456-7890",
    location: "Boston, USA",
    applied: "May 16, 2023",
    initials: "M",
  },
];

const statusLabels = {
  all: "All",
  new: "New",
  screening: "Screening",
  interview: "Interview",
  offer: "Offer",
  rejected: "Rejected",
};

export default function Home() {
  const [activeTab, setActiveTab] = useState("all");
  const [summary, setSummary] = useState(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    let mounted = true;
    api
      .summary()
      .then((data) => {
        if (mounted) setSummary(data);
      })
      .catch((e) => {
        if (mounted) setErr(String(e));
      });
    return () => {
      mounted = false;
    };
  }, []);

  const filtered = useMemo(() => {
    if (activeTab === "all") return candidates;
    return candidates.filter((c) => c.status === activeTab);
  }, [activeTab]);

  const counts = summary?.counts || {};
  const recentMatches = (summary?.recents?.match || []).concat(summary?.recents?.match_bulk || []);
  const recentTests = summary?.recents?.test_generate || [];

  return (
    <section className="canvas" aria-label="Accueil">
      <div className="header">
        <h2>Accueil</h2>
        <div className="tabs" id="home-tabs">
          {Object.keys(statusLabels).map((key) => (
            <button
              key={key}
              className={`tab ${activeTab === key ? "active" : ""}`}
              onClick={() => setActiveTab(key)}
              type="button"
            >
              {statusLabels[key]}
            </button>
          ))}
        </div>
      </div>
      <div className="section">
        {err && <div className="alert alert-danger mb-3">{err}</div>}
        <div className="cards" style={{ marginBottom: 18 }}>
          <article className="card">
              <div className="name">CV parsés</div>
            <div className="h4 mt-1">{counts.cv_parse || 0}</div>
          </article>
          <article className="card">
              <div className="name">JD parsés</div>
            <div className="h4 mt-1">{counts.jd_parse || 0}</div>
          </article>
          <article className="card">
              <div className="name">Matchs</div>
            <div className="h4 mt-1">{(counts.match || 0) + (counts.match_bulk || 0)}</div>
          </article>
          <article className="card">
              <div className="name">Tests générés</div>
            <div className="h4 mt-1">{counts.test_generate || 0}</div>
          </article>
        </div>

        {recentMatches.length > 0 && (
          <div style={{ marginBottom: 18 }}>
            <h4 style={{ margin: "0 0 8px" }}>Matchs récents</h4>
            <div className="cards">
              {recentMatches.slice(0, 3).map((m) => (
                <article className="card" key={m.id}>
                  <div className="name">Score global</div>
                  <div className="h4 mt-1">
                    {((m.payload?.result?.global_score || 0) * 100).toFixed(0)}%
                  </div>
                  <div className="muted small">
                    {m.payload?.result?.candidate_name || "N/A"}
                  </div>
                  <div className="muted small">{new Date(m.created_at).toLocaleString()}</div>
                </article>
              ))}
            </div>
          </div>
        )}

        {recentTests.length > 0 && (
          <div style={{ marginBottom: 18 }}>
            <h4 style={{ margin: "0 0 8px" }}>Tests générés</h4>
            <div className="cards">
              {recentTests.slice(0, 3).map((t) => (
                <article className="card" key={t.id}>
                  <div className="name">Questions</div>
                  <div className="h4 mt-1">{t.payload?.count ?? 0}</div>
                  <div className="muted small">{new Date(t.created_at).toLocaleString()}</div>
                </article>
              ))}
            </div>
          </div>
        )}

        <div className="cards">
          {filtered.map((c) => (
            <article className="card" key={c.email}>
              <header>
                <div style={{ display: "flex", gap: "10px", alignItems: "center" }}>
                  <div className="avatar">{c.initials}</div>
                  <div>
                    <div className="name">{c.name}</div>
                    <div className="role">{c.role}</div>
                  </div>
                </div>
                <span className={`badge ${c.status}`}>{statusLabels[c.status] || c.status}</span>
              </header>
              <ul className="kv">
                <li>
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7">
                    <path d="M4 6h16v10a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6z" />
                    <path d="M22 6l-10 7L2 6" />
                  </svg>
                  {c.email}
                </li>
                <li>
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7">
                    <path d="M22 16.92V21a1 1 0 0 1-1.1 1 19.79 19.79 0 0 1-8.63-3.07A19.5 19.5 0 0 1 3.07 11.73 19.79 19.79 0 0 1 0 3.1 1 1 0 0 1 1 2h4.09a1 1 0 0 1 1 .75 12.44 12.44 0 0 0 .7 2.09 1 1 0 0 1-.23 1.09L5.5 7.91a16 16 0 0 0 6.59 6.59l1.88-1.06a1 1 0 0 1 1.09.23 12.44 12.44 0 0 0 2.09.7 1 1 0 0 1 .75 1V16.92z" />
                  </svg>
                  {c.phone}
                </li>
                <li>
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7">
                    <path d="M21 10c0 6-9 12-9 12S3 16 3 10a9 9 0 1 1 18 0z" />
                    <circle cx="12" cy="10" r="3" />
                  </svg>
                  {c.location}
                </li>
                <li>
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7">
                    <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
                    <line x1="16" y1="2" x2="16" y2="6" />
                    <line x1="8" y1="2" x2="8" y2="6" />
                    <line x1="3" y1="10" x2="21" y2="10" />
                  </svg>
                  Applied: {c.applied}
                </li>
              </ul>
              <div style={{ fontSize: "12px", color: "#6b7280" }}>Rating</div>
              <div className="rating">
                {[1, 2, 3, 4, 5].map((i) => (
                  <svg
                    key={i}
                    width="16"
                    height="16"
                    viewBox="0 0 20 20"
                    fill={i <= 4 ? "#fbbf24" : "#e5e7eb"}
                  >
                    <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.802 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.802-2.034a1 1 0 00-1.175 0l-2.802 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.88 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
                  </svg>
                ))}
              </div>
              <footer>
                <a href="#">Voir le détail →</a>
              </footer>
            </article>
          ))}
        </div>
      </div>
      <div className="footer">(c) 2025 ATS Platform. Tous droits reserves.</div>
    </section>
  );
}
