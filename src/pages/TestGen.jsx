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
      setErr("Merci de charger une fiche de poste (JD) avant de générer des questions.");
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
        <h2>Génération de Tests</h2>
      </div>
      <div className="paper-wrap">
        <div className="paper">
          <div className="tile">
            <UploadBox
              label="Selectionnez la JD"
              onFile={handleJD}
              accept=".pdf,.docx,.txt"
              helper="Limite 200MB par fichier – PDF, DOCX, TXT"
            />
            {jdLoading && <div className="muted small">Analyse du JD...</div>}
            {jd && !jdLoading && (
              <div className="text-success small">
                JD chargée. Cliquez sur "Générer les questions" pour démarrer.
              </div>
            )}
            <button
              className="btn primary"
              onClick={generate}
              disabled={jdLoading || generating || !jd}
              type="button"
            >
              {generating ? "Génération..." : "Générer les questions"}
            </button>
            {err && <div className="alert alert-danger mb-0 py-2">{err}</div>}
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
