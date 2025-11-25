// src/pages/User.jsx
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

  const cardClass = fullPage ? "panel auth-card" : "panel";

  return (
    <div className={cardClass}>
      <div>
        <h3>{fullPage ? "Sign in to ATS" : "User"}</h3>
        {user && !fullPage && (
          <div className="result">
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
        )}
      </div>

      <form className="auth-form" onSubmit={submit}>
        <label className="uplabel">Username</label>
        <input
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          placeholder="admin"
        />

        <label className="uplabel">Password</label>
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="admin123"
        />

        <button className="primary" type="submit" disabled={busy}>
          {busy ? "Signing in..." : "Sign in"}
        </button>
        {err && <div className="error">{err}</div>}
      </form>
    </div>
  );
}
