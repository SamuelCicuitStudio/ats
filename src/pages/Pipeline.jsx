// src/pages/Pipeline.jsx
import React, { useState } from "react";
import UploadBox from "../components/UploadBox.jsx";
import { api } from "../services/api.js";

export default function Pipeline({ onStoreHistory }) {
  const MAX_CV_FILES = 100;

  const [cvFiles, setCvFiles] = useState([]);
  const [jdFile, setJdFile] = useState(null);
  const [jd, setJd] = useState(null);
  const [results, setResults] = useState([]);
  const [cvProgress, setCvProgress] = useState({ done: 0, total: 0 });
  const [jdLoading, setJdLoading] = useState(false);
  const [matchLoading, setMatchLoading] = useState(false);
  const [err, setErr] = useState("");
  const [info, setInfo] = useState("");

  function handleCV(files, totalSelected) {
    setErr("");
    setInfo("");
    setResults([]);
    setCvProgress({ done: 0, total: 0 });

    const list = Array.isArray(files) ? files : files ? [files] : [];
    if (!list.length) {
      setCvFiles([]);
      return;
    }

    const originalCount =
      typeof totalSelected === "number" ? totalSelected : list.length;
    const capped = list.slice(0, MAX_CV_FILES);
    if (originalCount > MAX_CV_FILES) {
      setInfo(
        `You selected ${originalCount} CVs; only the first ${MAX_CV_FILES} will be processed.`
      );
    }
    setCvFiles(capped);
  }
  function handleJD(file) {
    setErr("");
    setResults([]);
    setJdFile(file || null);
    setJd(null);
  }

  function resetAll() {
    setCvFiles([]);
    setJdFile(null);
    setJd(null);
    setResults([]);
    setCvProgress({ done: 0, total: 0 });
    setErr("");
    setInfo("");
  }

  async function doMatch() {
    if (!cvFiles.length || !jdFile) {
      setErr(
        "Upload one JD and at least one CV (up to 100) before running matching."
      );
      return;
    }
    setErr("");
    setInfo("");
    setResults([]);
    setMatchLoading(true);
    setJdLoading(true);
    setCvProgress({ done: 0, total: cvFiles.length });
    try {
      const { jd: jdJson } = await api.parseJD(jdFile);
      setJd(jdJson);
      setJdLoading(false);

      const parsed = [];
      for (let i = 0; i < cvFiles.length; i += 1) {
        setCvProgress({ done: i, total: cvFiles.length });
        const { cv: cvJson } = await api.parseCV(cvFiles[i]);
        parsed.push({ file: cvFiles[i], cv: cvJson });
        setCvProgress({ done: i + 1, total: cvFiles.length });
      }

      const bulk = await api.matchBulk(
        parsed.map((p) => p.cv),
        jdJson,
        null
      );

      const mapped = (bulk.results || []).map((entry) => {
        const meta = parsed[entry.index] || {};
        return {
          index: entry.index,
          fileName: meta.file?.name || `CV ${entry.index + 1}`,
          cv: meta.cv,
          result: entry.result,
        };
      });

      mapped.sort(
        (a, b) =>
          (b.result?.global_score || 0) - (a.result?.global_score || 0)
      );

      setResults(mapped);
      onStoreHistory?.({
        type: "match-bulk",
        at: new Date().toISOString(),
        cvs: parsed.map((p) => p.cv),
        jd: jdJson,
        results: mapped,
      });
    } catch (e) {
      setErr(String(e));
    } finally {
      setJdLoading(false);
      setMatchLoading(false);
    }
  }

  const isParsingCvs =
    cvProgress.total > 0 && cvProgress.done < cvProgress.total;

  return (
    <section
      id="screen-pipeline"
      className="canvas"
      aria-label="Pipeline de Recrutement Integree"
    >
      <div className="header">
        <h2>Pipeline de Recrutement Integree</h2>
        <div className="steps">
            <div className={`step ${cvFiles.length ? "active" : ""}`}>
              <div className="dot dot-upload" aria-hidden="true">
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <path d="M12 16V4" stroke="#0f172a" strokeWidth="2" strokeLinecap="round" />
                  <path d="M7 9l5-5 5 5" stroke="#0f172a" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                  <path d="M5 19h14" stroke="#0f172a" strokeWidth="2" strokeLinecap="round" />
                </svg>
              </div>
              Upload
            </div>
            <span className="muted">→</span>
            <div className={`step ${jd ? "active" : ""}`}>
              <div className="dot dot-parse" aria-hidden="true">
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <path d="M7 3h7l5 5v11a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2z" stroke="#0f172a" strokeWidth="2" />
                  <path d="M14 3v5h5" stroke="#0f172a" strokeWidth="2" />
                  <path d="M9 12h6M9 15h6" stroke="#0f172a" strokeWidth="2" strokeLinecap="round" />
                </svg>
              </div>
              Parsing
            </div>
            <span className="muted">→</span>
            <div className={`step ${results.length ? "active" : ""}`}>
              <div className="dot dot-match" aria-hidden="true">
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <circle cx="12" cy="12" r="8" stroke="#0f172a" strokeWidth="2" />
                  <circle cx="12" cy="12" r="3" fill="#0f172a" />
                  <path d="M12 4v2M12 18v2M4 12h2M18 12h2" stroke="#0f172a" strokeWidth="2" strokeLinecap="round" />
                </svg>
              </div>
              Matching
            </div>
          </div>
      </div>

      <div className="section">
        <h3>Upload des Fichiers</h3>
        <div className="grid">
          <div className="drop">
            <UploadBox
              label="Selectionnez les CVs"
              onFiles={handleCV}
              multiple
              maxFiles={MAX_CV_FILES}
              accept=".pdf,.docx,.txt"
              helper="Limit 200MB per file – PDF, DOCX, TXT"
            />
          </div>
          <div className="drop">
            <UploadBox
              label="Selectionnez la description de poste"
              onFile={handleJD}
              accept=".pdf,.docx,.txt"
              helper="Limit 200MB per file – PDF, DOCX, TXT"
            />
          </div>
        </div>

        {cvFiles.length > 0 && (
          <div className="text-muted small mt-2">
            {cvFiles.length} CV file{cvFiles.length > 1 ? "s" : ""} selected (max {MAX_CV_FILES})
          </div>
        )}
        {cvFiles.length > 0 && (
          <div className="cv-chip-row mt-2">
            {cvFiles.slice(0, 6).map((f) => (
              <span className="cv-chip" key={f.name + f.size}>
                {f.name}
              </span>
            ))}
            {cvFiles.length > 6 && (
              <span className="cv-chip more">+{cvFiles.length - 6} more</span>
            )}
          </div>
        )}
        {isParsingCvs && (
          <div className="muted small mt-2">
            Parsing CVs... ({cvProgress.done}/{cvProgress.total})
          </div>
        )}
        {cvProgress.total > 0 && !isParsingCvs && cvProgress.done === cvProgress.total && (
          <div className="text-success small mt-2">
            Parsed {cvProgress.total} CV{cvProgress.total > 1 ? "s" : ""}
          </div>
        )}
        {jdLoading && <div className="muted small mt-2">Parsing JD...</div>}
        {jd && !jdLoading && <div className="text-success small mt-2">JD parsed</div>}
        {info && <div className="alert alert-info mt-3 mb-0 py-2">{info}</div>}
        {err && <div className="alert alert-danger mt-3 mb-0 py-2">{err}</div>}

        <div className="actions-row">
          <button className="btn ghost" type="button" onClick={resetAll}>
            Annuler
          </button>
          <button
            className="btn primary"
            onClick={doMatch}
            disabled={matchLoading || jdLoading || isParsingCvs || !cvFiles.length || !jdFile}
            type="button"
          >
            {matchLoading ? "Matching..." : "Suivant Parsing"}
          </button>
        </div>
      </div>

      {results.length > 0 && (
        <div className="section">
          <h3>Resultats de Matching</h3>
          <div className="table-responsive">
            <table className="table align-middle my-3">
              <thead>
                <tr>
                  <th>#</th>
                  <th>CV File</th>
                  <th>Candidate</th>
                  <th>Global</th>
                  <th>Breakdown</th>
                </tr>
              </thead>
              <tbody>
                {results.map((row, i) => (
                  <tr key={row.index ?? i}>
                    <td className="text-muted">{i + 1}</td>
                    <td>{row.fileName}</td>
                    <td>
                      <div className="fw-semibold">
                        {row.result?.candidate_name || "Unknown"}
                      </div>
                      <div className="muted small">
                        {row.result?.cv_title || "No title"}
                      </div>
                    </td>
                    <td>
                      <div className="score-badge">
                        {((row.result?.global_score || 0) * 100).toFixed(0)}%
                      </div>
                    </td>
                    <td>
                      <div className="score-pill-row">
                        {Object.entries(row.result?.scores || {}).map(([k, v]) => (
                          <span className="score-pill" key={k}>
                            {k}: {(v * 100).toFixed(0)}%
                          </span>
                        ))}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <div className="footer">(c) 2025 ATS Platform. Tous droits reserves.</div>
    </section>
  );
}
