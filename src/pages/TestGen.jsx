// src/pages/TestGen.jsx
import React, { useState } from "react";
import UploadBox from "../components/UploadBox.jsx";
import { api } from "../services/api.js";

export default function TestGen({ onStoreHistory }) {
  const [jd, setJd] = useState(null);
  const [questions, setQuestions] = useState([]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  async function handleJD(file) {
    setErr("");
    setBusy(true);
    try {
      const { jd: jdJson } = await api.parseJD(file);
      setJd(jdJson);
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function generate() {
    if (!jd) {
      setErr("Upload a JD first.");
      return;
    }
    setErr("");
    setBusy(true);
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
      setBusy(false);
    }
  }

  return (
    <div className="panel card bg-panel border-soft shadow-1 p-4">
      <div className="d-flex flex-column gap-3">
        <UploadBox label="Upload JD for test generation" onFile={handleJD} />
        <button
          className="btn btn-primary"
          onClick={generate}
          disabled={busy}
        >
          {busy ? "Generating..." : "Generate Questions"}
        </button>
        {err && <div className="alert alert-danger mb-0 py-2">{err}</div>}

        {questions.length > 0 && (
          <div className="result card bg-dark-subtle border-0 mt-2">
            <div className="card-body">
              <h3 className="h5 mb-3">Questions</h3>
              <ol className="mb-0">
                {questions.map((q, i) => (
                  <li key={i}>{q.question}</li>
                ))}
              </ol>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
