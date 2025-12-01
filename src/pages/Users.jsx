// src/pages/Users.jsx
import React, { useEffect, useMemo, useState } from "react";
import { api } from "../services/api";

export default function Users({ session, onUserUpdate }) {
  const token = session?.token;
  const currentUser = session?.user;
  const isAdmin = useMemo(
    () => !!(currentUser?.roles || []).includes("admin"),
    [currentUser]
  );

  const [users, setUsers] = useState([]);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  const [selfName, setSelfName] = useState(currentUser?.display_name || "");
  const [selfPwd, setSelfPwd] = useState("");

  const [newUser, setNewUser] = useState({
    username: "",
    password: "",
    display_name: "",
    roles: ["user"],
  });
  const [editing, setEditing] = useState({});

  useEffect(() => {
    setSelfName(currentUser?.display_name || "");
  }, [currentUser]);
  useEffect(() => {
    if (isAdmin && token) loadUsers(); /* eslint-disable-next-line */
  }, [isAdmin, token]);

  async function loadUsers() {
    setErr("");
    setBusy(true);
    try {
      const list = await api.listUsers(token);
      setUsers(list);
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function saveSelf(e) {
    e?.preventDefault();
    setErr("");
    setBusy(true);
    try {
      const payload = { display_name: selfName };
      if (selfPwd.trim()) payload.password = selfPwd.trim();
      const updated = await api.updateSelf(token, payload);
      onUserUpdate?.(updated);
      setSelfPwd("");
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  }

  function toggleRole(obj, role) {
    const set = new Set(obj.roles || []);
    if (set.has(role)) set.delete(role);
    else set.add(role);
    return Array.from(set);
  }

  async function addUser(e) {
    e?.preventDefault();
    setErr("");
    setBusy(true);
    try {
      await api.createUser(token, {
        username: newUser.username.trim(),
        password: newUser.password.trim(),
        display_name: newUser.display_name.trim(),
        roles: newUser.roles,
      });
      setNewUser({
        username: "",
        password: "",
        display_name: "",
        roles: ["user"],
      });
      await loadUsers();
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  }

  function onEditField(username, field, value) {
    setEditing((prev) => ({
      ...prev,
      [username]: { ...(prev[username] || {}), [field]: value },
    }));
  }

  async function saveUser(username) {
    setErr("");
    setBusy(true);
    try {
      const state = editing[username] || {};
      const payload = {
        new_username: state.new_username || username,
        display_name: state.display_name,
        roles: state.roles,
      };
      if (state.password) payload.password = state.password;
      const updated = await api.updateUser(token, username, payload);
      if (currentUser?.username === username) onUserUpdate?.(updated);
      setEditing((prev) => {
        const copy = { ...prev };
        delete copy[username];
        return copy;
      });
      await loadUsers();
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function removeUser(username) {
    if (!window.confirm(`Supprimer l'utilisateur "${username}" ?`)) return;
    setErr("");
    setBusy(true);
    try {
      await api.deleteUser(token, username);
      await loadUsers();
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="panel card bg-panel border-soft shadow-1 p-4">
      <div className="card bg-dark-subtle border-0 mb-4">
        <div className="card-body">
          <h3 className="h5 mb-3">Mon compte</h3>
          <form className="row g-3" onSubmit={saveSelf}>
            <div className="col-12 col-md-6">
              <label className="form-label">Nom affiché</label>
              <input
                className="form-control"
                value={selfName}
                onChange={(e) => setSelfName(e.target.value)}
                placeholder="Votre nom"
              />
            </div>
            <div className="col-12 col-md-6">
              <label className="form-label">Nouveau mot de passe</label>
              <input
                className="form-control"
                type="password"
                value={selfPwd}
                onChange={(e) => setSelfPwd(e.target.value)}
                placeholder="Définir un nouveau mot de passe"
              />
            </div>
            <div className="col-12">
              <button className="btn btn-primary" type="submit" disabled={busy}>
                Enregistrer
              </button>
            </div>
          </form>
        </div>
      </div>

      {isAdmin && (
        <div className="card users-admin-card border-0">
          <div className="card-body">
            <h3 className="h5 mb-3">Utilisateurs</h3>

            <form className="row g-3" onSubmit={addUser}>
              <div className="col-12 col-md-3">
                <label className="form-label">Identifiant</label>
                <input
                  className="form-control"
                  value={newUser.username}
                  onChange={(e) =>
                    setNewUser((u) => ({ ...u, username: e.target.value }))
                  }
                  placeholder="identifiant"
                  required
                />
              </div>
              <div className="col-12 col-md-3">
                <label className="form-label">Mot de passe</label>
                <input
                  className="form-control"
                  type="password"
                  value={newUser.password}
                  onChange={(e) =>
                    setNewUser((u) => ({ ...u, password: e.target.value }))
                  }
                  placeholder="Définir un mot de passe"
                  required
                />
              </div>
              <div className="col-12 col-md-4">
                <label className="form-label">Nom affiché</label>
                <input
                  className="form-control"
                  value={newUser.display_name}
                  onChange={(e) =>
                    setNewUser((u) => ({ ...u, display_name: e.target.value }))
                  }
                  placeholder="Optionnel"
                />
              </div>
              <div className="col-12 col-md-3">
                <label className="form-label">Rôles</label>
                <div className="users-role-group">
                  <div className="form-check">
                    <input
                      className="form-check-input"
                      type="checkbox"
                      checked={newUser.roles.includes("user")}
                      onChange={() =>
                        setNewUser((u) => ({
                          ...u,
                          roles: toggleRole(u, "user"),
                        }))
                      }
                      id="role-user"
                    />
                    <label className="form-check-label ms-1" htmlFor="role-user">
                      utilisateur
                    </label>
                  </div>
                  <div className="form-check">
                    <input
                      className="form-check-input"
                      type="checkbox"
                      checked={newUser.roles.includes("admin")}
                      onChange={() =>
                        setNewUser((u) => ({
                          ...u,
                          roles: toggleRole(u, "admin"),
                        }))
                      }
                      id="role-admin"
                    />
                    <label className="form-check-label ms-1" htmlFor="role-admin">
                      admin
                    </label>
                  </div>
                </div>
              </div>
              <div className="col-12">
                <button
                  className="btn btn-primary"
                  type="submit"
                  disabled={busy}
                >
                  Ajouter
                </button>
              </div>
            </form>

            <div className="table-responsive mt-4">
              <table className="table users-table table-striped align-middle mb-0 w-100">
                <thead>
                  <tr>
                    <th>Utilisateur</th>
                    <th>Rôles / Mot de passe</th>
                    <th className="text-end">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {users.map((u) => {
                    const state = editing[u.username] || {
                      new_username: u.username,
                      display_name: u.display_name,
                      roles: u.roles,
                      password: "",
                    };
                    return (
                      <tr key={u.username}>
                        <td className="users-cell">
                          <label className="form-label text-uppercase small fw-semibold">
                            Identifiant
                          </label>
                          <input
                            className="form-control mb-3"
                            value={state.new_username}
                            onChange={(e) =>
                              onEditField(
                                u.username,
                                "new_username",
                                e.target.value
                              )
                            }
                          />
                          <label className="form-label text-uppercase small fw-semibold">
                            Nom affiché
                          </label>
                          <input
                            className="form-control"
                            value={state.display_name || ""}
                            onChange={(e) =>
                              onEditField(
                                u.username,
                                "display_name",
                                e.target.value
                              )
                            }
                            placeholder="Nom affiché"
                          />
                        </td>
                        <td className="users-cell">
                          <label className="form-label text-uppercase small fw-semibold">
                            Rôles
                          </label>
                          <div className="users-role-checkboxes mb-3">
                            {["user", "admin"].map((r) => (
                              <label className="role-pill" key={r}>
                                <input
                                  type="checkbox"
                                  checked={(state.roles || []).includes(r)}
                                  onChange={() =>
                                    onEditField(
                                      u.username,
                                      "roles",
                                      toggleRole(state, r)
                                    )
                                  }
                                />
                                <span>{r}</span>
                              </label>
                            ))}
                          </div>
                          <label className="form-label text-uppercase small fw-semibold">
                            Réinitialiser le mot de passe
                          </label>
                          <input
                            className="form-control"
                            type="password"
                            value={state.password || ""}
                            onChange={(e) =>
                              onEditField(
                                u.username,
                                "password",
                                e.target.value
                              )
                            }
                            placeholder="Nouveau mot de passe"
                          />
                        </td>
                        <td className="users-cell text-end align-middle">
                          <div className="users-actions">
                            <button
                              className="btn btn-primary"
                              type="button"
                              onClick={() => saveUser(u.username)}
                              disabled={busy}
                            >
                              Enregistrer
                            </button>
                            <button
                              className="btn btn-danger"
                              type="button"
                              onClick={() => removeUser(u.username)}
                              disabled={busy}
                            >
                              Supprimer
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {err && <div className="alert alert-danger mt-3 mb-0 py-2">{err}</div>}
    </div>
  );
}
