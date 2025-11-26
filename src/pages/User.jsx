import React, { useState } from "react";
import { api } from "../services/api";

export default function User({ user, onLogin, fullPage = false }) {
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("admin123");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setErr("");
    setBusy(true);
    try {
      const profile = await api.login(username, password);
      onLogin?.(profile);
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  }

  if (fullPage) {
    return (
      <div className="login-panel fadeInDown">
        <svg
          className="topbar-icon fadeIn first"
          viewBox="0 0 64 40"
          role="img"
          aria-label="ATS visual icon"
        >
          <rect x="2" y="6" width="22" height="28" rx="4" fill="var(--panel)" stroke="var(--accent)" strokeWidth="2" />
          <rect x="40" y="6" width="22" height="28" rx="4" fill="var(--panel)" stroke="var(--accent-strong)" strokeWidth="2" />
          <path
            d="M32 8c7.18 0 13 5.82 13 13s-5.82 13-13 13-13-5.82-13-13 5.82-13 13-13zm0 6.5a6.5 6.5 0 100 13 6.5 6.5 0 000-13zm0-4l1.2 2.8 3-.4-1.8 2.4 1.8 2.4-3-.4-1.2 2.8-1.2-2.8-3 .4 1.8-2.4-1.8-2.4 3 .4 1.2-2.8z"
            fill="url(#loginGearGrad)"
          />
          <defs>
            <linearGradient id="loginGearGrad" x1="19" y1="8" x2="45" y2="34" gradientUnits="userSpaceOnUse">
              <stop stopColor="var(--accent)" />
              <stop offset="1" stopColor="var(--accent-strong)" />
            </linearGradient>
          </defs>
        </svg>
        <form className="login-form" onSubmit={submit}>
          <input
            className="login-input fadeIn second"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            placeholder="Username"
          />
          <input
            className="login-input fadeIn third"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Password"
          />
          <button
          className="btn btn-primary login-button fadeIn fourth"
          type="submit"
          disabled={busy}
        >
            {busy ? "Signing in..." : "Log In"}
          </button>
          {err && <div className="alert alert-danger mt-2">{err}</div>}
        </form>
        <div className="login-footer">
          <a className="underlineHover" href="#!">
            Forgot password?
          </a>
        </div>
      </div>
    );
  }

  return (
    <div className="panel card p-4" style={{ maxWidth: 520, width: "100%" }}>
      <div>
        <h3 className="h5">User</h3>
        {user && (
          <div className="result card bg-white border-0 mt-3">
            <div className="card-body">
              <div>
                <b>Username:</b> {user.username}
              </div>
              <div>
                <b>Roles:</b> {(user.roles || []).join(", ")}
              </div>
              {user.display_name && (
                <div>
                  <b>Name:</b> {user.display_name}
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      <form className="row g-3 mt-3" onSubmit={submit}>
        <div className="col-12">
          <label className="form-label">Username</label>
          <input
            className="form-control"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            placeholder="admin"
          />
        </div>
        <div className="col-12">
          <label className="form-label">Password</label>
          <input
            className="form-control"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="admin123"
          />
        </div>
        <div className="col-12">
          <button className="btn btn-primary" type="submit" disabled={busy}>
            {busy ? "Signing in..." : "Sign in"}
          </button>
          {err && (
            <div className="alert alert-danger mt-3 mb-0 py-2">{err}</div>
          )}
        </div>
      </form>
    </div>
  );
}
