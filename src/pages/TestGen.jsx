// src/pages/TestGen.jsx
import React, { useState } from "react";
import UploadBox from "../components/UploadBox.jsx";
import { api } from "../services/api.js";

export default function TestGen({
  onStoreHistory,
  job,
  jobActive,
  onJobStart,
  onJobUpdate,
  onJobClear,
  onJobCancel,
}) {
  const [jd, setJd] = useState(null);
  const [questions, setQuestions] = useState([]);
  const [jdLoading, setJdLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [err, setErr] = useState("");

  async function handleJD(file) {
    if (jobActive) {
      setErr("Une tache est deja en cours. Annulez-la avant de charger un JD.");
      return;
    }
    setErr("");
    setQuestions([]);
    setJd(null);
    setJdLoading(true);
    const controller = onJobStart?.({
      key: "testgen",
      label: "Analyse du JD",
      detail: "Analyse de la fiche de poste...",
      progress: { done: 0, total: 1, message: "Analyse du JD..." },
    });
    try {
      const { jd: jdJson } = await api.parseJD(file, { signal: controller?.signal });
      setJd(jdJson);
      onJobUpdate?.({
        status: "running",
        detail: "JD analyse",
        progress: { done: 1, total: 1, message: "JD analyse" },
      });
    } catch (e) {
      if (e.name === "AbortError") setErr("Tache annulee.");
      else setErr(String(e));
    } finally {
      setJdLoading(false);
      onJobClear?.();
    }
  }

  async function generate() {
    if (jobActive) {
      setErr("Une autre tache est en cours. Annulez-la avant de generer des questions.");
      return;
    }
    if (!jd) {
      setErr("Merci de charger une fiche de poste (JD) avant de generer des questions.");
      return;
    }
    setErr("");
    setGenerating(true);
    const controller = onJobStart?.({
      key: "testgen",
      label: "Generation de tests",
      detail: "Creation des questions...",
      progress: { done: 0, total: 1, message: "Generation..." },
    });
    try {
      const data = await api.genQuestions(jd, { signal: controller?.signal });
      const list = data.questions || [];
      setQuestions(list);
      onStoreHistory?.({
        type: "test",
        at: new Date().toISOString(),
        jd,
        questions: list,
      });
      onJobUpdate?.({
        status: "running",
        detail: "Questions generees",
        progress: { done: 1, total: 1, message: "Termine" },
      });
    } catch (e) {
      if (e.name === "AbortError") setErr("Tache annulee.");
      else setErr(String(e));
    } finally {
      setGenerating(false);
      onJobClear?.();
    }
  }

  const busy = jdLoading || generating || jobActive;

  return (
    <section className="canvas">
      <div className="header">
        <h2>Generation de Tests</h2>
      </div>
      <div className="paper-wrap">
        <div className="paper">
          <div className="tile">
            <UploadBox
              label="Selectionnez la JD"
              onFile={handleJD}
              accept=".pdf,.docx,.txt"
              helper="Limite 200MB par fichier - PDF, DOCX, TXT"
              disabled={busy}
            />
            {jdLoading && <div className="muted small">Analyse du JD...</div>}
            {jd && !jdLoading && (
              <div className="text-success small">
                JD charge. Cliquez sur "Generer les questions" pour demarrer.
              </div>
            )}
            <button
              className="btn primary"
              onClick={generate}
              disabled={busy || !jd}
              type="button"
            >
              {generating ? "Generation..." : "Generer les questions"}
            </button>
            {jobActive && job?.key === "testgen" && (
              <button className="btn" type="button" onClick={onJobCancel}>
                Annuler la tache
              </button>
            )}
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
      <div className="footer">(c) 2025 ATS Platform. Tous droits reserves.</div>
    </section>
  );
}
