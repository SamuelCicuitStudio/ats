// src/pages/Pipeline.jsx
import React, { useState } from "react";
import UploadBox from "../components/UploadBox.jsx";
import { api } from "../services/api.js";

export default function Pipeline({ onStoreHistory }) {
  const [cv, setCv] = useState(null);
  const [jd, setJd] = useState(null);
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  async function handleCV(file) {
    setErr("");
    setBusy(true);
    try {
      const { cv: cvJson } = await api.parseCV(file);
      setCv(cvJson);
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  }

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

  async function doMatch() {
    if (!cv || !jd) {
      setErr("Upload CV and JD first.");
      return;
    }
    setErr("");
    setBusy(true);
    try {
      const { result } = await api.match(cv, jd, null);
      setResult(result);
      onStoreHistory?.({
        type: "match",
        at: new Date().toISOString(),
        cv,
        jd,
        result,
      });
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="panel">
      <div className="row">
        <UploadBox label="Upload CV (.pdf/.docx/.txt)" onFile={handleCV} />
        <UploadBox label="Upload JD (.pdf/.docx/.txt)" onFile={handleJD} />
      </div>

      <button className="primary" onClick={doMatch} disabled={busy}>
        Run Matching
      </button>
      {err && <div className="error">{err}</div>}

      {result && (
        <div className="result">
          <h3>Match Result</h3>
          <div>
            <b>Candidate:</b> {result.candidate_name || "—"}
          </div>
          <div>
            <b>CV Title:</b> {result.cv_title || "—"}
          </div>
          <div>
            <b>JD Title:</b> {result.jd_title || "—"}
          </div>
          <table className="scores">
            <tbody>
              {Object.entries(result.scores || {}).map(([k, v]) => (
                <tr key={k}>
                  <td>{k}</td>
                  <td>{(v * 100).toFixed(0)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div>
            <b>Global:</b> {(result.global_score * 100).toFixed(0)}%
          </div>
        </div>
      )}
    </div>
  );
}
