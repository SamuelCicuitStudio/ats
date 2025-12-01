// src/pages/TestGen.jsx
import React, { useState } from "react";
import UploadBox from "../components/UploadBox.jsx";
import { api } from "../services/api.js";

export default function TestGen({ onStoreHistory }) {
  const [jd, setJd] = useState(null);
  const [questions, setQuestions] = useState([]);
  const [jdLoading, setJdLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [err, setErr] = useState("");

  async function handleJD(file) {
    setErr("");
    setQuestions([]);
    setJd(null);
    setJdLoading(true);
    try {
      const { jd: jdJson } = await api.parseJD(file);
      setJd(jdJson);
    } catch (e) {
      setErr(String(e));
    } finally {
      setJdLoading(false);
    }
  }

  async function generate() {
    if (!jd) {
      setErr("Upload a JD first.");
      return;
    }
    setErr("");
    setGenerating(true);
    try {
      const data = await api.genQuestions(jd);
      const list = data.questions || [];
      setQuestions(list);
      onStoreHistory?.({
        type: "test",
        at: new Date().toISOString(),
        jd,
        questions: list,
      });
    } catch (e) {
      setErr(String(e));
    } finally {
      setGenerating(false);
    }
  }

  return (
    <section className="canvas">
      <div className="header">
        <h2>Generation de Tests</h2>
      </div>
      <div className="paper-wrap">
        <div className="paper">
          <div className="tile" style={{ borderRight: "1px dashed #e4e6ed" }}>
            <UploadBox
              label="Selectionnez la JD"
              onFile={handleJD}
              accept=".pdf,.docx,.txt"
              helper="Limit 200MB per file – PDF, DOCX, TXT"
            />
            {jdLoading && <div className="muted small">Parsing JD...</div>}
            {jd && !jdLoading && (
              <div className="text-success small">
                JD chargee. Cliquez sur "Generate Questions" pour demarrer.
              </div>
            )}
            <button
              className="btn primary"
              onClick={generate}
              disabled={jdLoading || generating || !jd}
              type="button"
            >
              {generating ? "Generating..." : "Generate Questions"}
            </button>
            {err && <div className="alert alert-danger mb-0 py-2">{err}</div>}
          </div>
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
            <p className="muted">La generation automatique de tests sera bientot disponible</p>
          </div>
        </div>
      </div>
      {questions.length > 0 && (
        <div className="section">
          <h3>Questions</h3>
          <ol className="mb-0">
            {questions.map((q, i) => (
              <li key={i}>{q.question}</li>
            ))}
          </ol>
        </div>
      )}
      <div className="footer">© 2025 ATS Platform. Tous droits reserves.</div>
    </section>
  );
}
