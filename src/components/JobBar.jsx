import React from "react";

export default function JobBar({ job, onCancel }) {
  if (!job) return null;

  const { label, detail, status, progress } = job;
  const total = progress?.total || 0;
  const done = progress?.done || 0;
  const message = progress?.message;
  const percent = total > 0 ? Math.min(100, Math.round((done / total) * 100)) : null;
  const isBusy = status === "running" || status === "cancelling";

  return (
    <div className="jobbar" role="status" aria-live="polite">
      <div className="jobbar-content">
        <div className="jobbar-main">
          <div className="jobbar-title">
            <span className="dot dot-live" aria-hidden="true" />
            <span>{label || "Tache en cours"}</span>
          </div>
          {detail && <div className="jobbar-detail">{detail}</div>}
          {message && <div className="jobbar-message">{message}</div>}
          {percent !== null && (
            <div className="jobbar-progress">
              <div className="jobbar-progress-track">
                <div
                  className="jobbar-progress-fill"
                  style={{ width: `${percent}%` }}
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-valuenow={percent}
                  role="progressbar"
                />
              </div>
              <span className="jobbar-percent">
                {done}/{total} ({percent}%)
              </span>
            </div>
          )}
        </div>
        <div className="jobbar-actions">
          <button
            className="btn ghost"
            type="button"
            onClick={onCancel}
            disabled={!isBusy}
          >
            {status === "cancelling" ? "Annulation..." : "Annuler"}
          </button>
        </div>
      </div>
    </div>
  );
}
