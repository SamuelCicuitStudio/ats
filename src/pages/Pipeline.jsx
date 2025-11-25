// src/pages/Pipeline.jsx
import React, { useState } from "react";
import UploadBox from "../components/UploadBox.jsx";
import { api } from "../services/api.js";

export default function Pipeline({ onStoreHistory }) {
  const [cvFile, setCvFile] = useState(null);
  const [jdFile, setJdFile] = useState(null);
  const [cv, setCv] = useState(null);
  const [jd, setJd] = useState(null);
  const [result, setResult] = useState(null);
  const [cvLoading, setCvLoading] = useState(false);
  const [jdLoading, setJdLoading] = useState(false);
  const [matchLoading, setMatchLoading] = useState(false);
  const [err, setErr] = useState("");

  async function handleCV(file) {
    setErr("");
    setResult(null);
    setCvFile(file || null);
    setCv(null);
  }
  async function handleJD(file) {
    setErr("");
    setResult(null);
    setJdFile(file || null);
    setJd(null);
  }

  async function doMatch() {
    if (!cvFile || !jdFile) {
      setErr("Upload CV and JD first, then click Run Matching.");
      return;
    }
    setErr("");
    setResult(null);
    setMatchLoading(true);
    setCvLoading(true);
    setJdLoading(true);
    try {
      const [{ cv: cvJson }, { jd: jdJson }] = await Promise.all([
        api.parseCV(cvFile),
        api.parseJD(jdFile),
      ]);
      setCv(cvJson);
      setJd(jdJson);
      setCvLoading(false);
      setJdLoading(false);

      const { result } = await api.match(cvJson, jdJson, null);
      setResult(result);
      onStoreHistory?.({
        type: "match",
        at: new Date().toISOString(),
        cv: cvJson,
        jd: jdJson,
        result,
      });
    } catch (e) {
      setErr(String(e));
    } finally {
      setCvLoading(false);
      setJdLoading(false);
      setMatchLoading(false);
    }
  }

  return (
    <div className="panel pipeline-board card bg-panel border-soft shadow-1 p-4">
      <div className="pipeline-header">
        <div className="pipeline-steps">
          <div className={`step ${cvFile ? "active" : ""}`}>
            <span className="round-tab one">1</span>
            <p>Upload CV</p>
          </div>
          <div className={`step ${jdFile ? "active" : ""}`}>
            <span className="round-tab two">2</span>
            <p>Upload JD</p>
          </div>
          <div className={`step ${result ? "active" : ""}`}>
            <span className="round-tab three">3</span>
            <p>Match</p>
          </div>
        </div>
        <div className="pipeline-liner" />
      </div>

      <div className="row g-4 mt-2 align-items-stretch">
        <div className="col-12 col-lg-6">
          <div className="pipeline-drop">
            <UploadBox label="Upload CV (.pdf/.docx/.txt)" onFile={handleCV} />
          </div>
          {cvFile && !cvLoading && (
            <div className="text-muted small mt-2">CV selected</div>
          )}
          {cvLoading && (
            <div className="text-muted small mt-2">Parsing CV...</div>
          )}
          {cv && !cvLoading && (
            <div className="text-success small mt-2">CV parsed</div>
          )}
        </div>
        <div className="col-12 col-lg-6">
          <div className="pipeline-drop">
            <UploadBox label="Upload JD (.pdf/.docx/.txt)" onFile={handleJD} />
          </div>
          {jdFile && !jdLoading && (
            <div className="text-muted small mt-2">JD selected</div>
          )}
          {jdLoading && (
            <div className="text-muted small mt-2">Parsing JD...</div>
          )}
          {jd && !jdLoading && (
            <div className="text-success small mt-2">JD parsed</div>
          )}
        </div>
      </div>

      <div className="d-flex flex-wrap gap-3 align-items-center mt-4">
        <button
          className="btn btn-primary"
          onClick={doMatch}
          disabled={matchLoading || cvLoading || jdLoading || !cvFile || !jdFile}
          title={
            !cvFile || !jdFile
              ? "Upload both CV and JD first"
              : matchLoading
              ? "Matching..."
              : "Run matching"
          }
        >
          {matchLoading ? "Matching..." : "Run Matching"}
        </button>
        {err && <div className="alert alert-danger mb-0 py-2">{err}</div>}
      </div>

      {result && (
        <div className="result card bg-dark-subtle border-0 mt-4">
          <div className="card-body">
            <h3 className="h5 mb-3">Match Result</h3>
            <div>
              <b>Candidate:</b> {result.candidate_name || "-"}
            </div>
            <div>
              <b>CV Title:</b> {result.cv_title || "-"}
            </div>
            <div>
              <b>JD Title:</b> {result.jd_title || "-"}
            </div>
            <table className="table table-dark table-striped align-middle my-3">
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
        </div>
      )}
    </div>
  );
}
