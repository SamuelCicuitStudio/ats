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
      <div className="auth-wrapper">
        <div className="auth-card fadeInDown">
          <div className="brand">
            <div className="dot" aria-hidden="true"></div>
            <h1>ATS Platform</h1>
          </div>
          <div className="muted" style={{ marginBottom: 12 }}>
            Connectez-vous pour continuer
          </div>
          <form className="login-form" onSubmit={submit}>
            <input
              className="login-input fadeIn second"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="Identifiant"
            />
            <input
              className="login-input fadeIn third"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Password"
            />
            <button
              className="btn primary login-button fadeIn fourth"
              type="submit"
              disabled={busy}
            >
              {busy ? "Connexion..." : "Se connecter"}
            </button>
            {err && <div className="alert alert-danger mt-2">{err}</div>}
          </form>
          <div className="login-footer">
            <a className="underlineHover" href="#!" onClick={(e) => e.preventDefault()}>
              Forgot password?
            </a>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="panel card p-4" style={{ maxWidth: 520, width: "100%" }}>
      <div>
        <h3 className="h5">Utilisateur</h3>
        {user && (
          <div className="result card bg-white border-0 mt-3">
            <div className="card-body">
              <div>
                <b>Identifiant :</b> {user.username}
              </div>
              <div>
                <b>Rôles :</b> {(user.roles || []).join(", ")}
              </div>
              {user.display_name && (
                <div>
                  <b>Nom :</b> {user.display_name}
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      <form className="row g-3 mt-3" onSubmit={submit}>
        <div className="col-12">
          <label className="form-label">Identifiant</label>
          <input
            className="form-control"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            placeholder="admin"
          />
        </div>
        <div className="col-12">
          <label className="form-label">Mot de passe</label>
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
            {busy ? "Connexion..." : "Se connecter"}
          </button>
          {err && (
            <div className="alert alert-danger mt-3 mb-0 py-2">{err}</div>
          )}
        </div>
      </form>
    </div>
  );
}
