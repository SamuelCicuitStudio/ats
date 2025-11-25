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
    if (!window.confirm(`Delete user "${username}"?`)) return;
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
          <h3 className="h5 mb-3">Your account</h3>
          <form className="row g-3" onSubmit={saveSelf}>
            <div className="col-12 col-md-6">
              <label className="form-label">Display name</label>
              <input
                className="form-control"
                value={selfName}
                onChange={(e) => setSelfName(e.target.value)}
                placeholder="Your name"
              />
            </div>
            <div className="col-12 col-md-6">
              <label className="form-label">New password</label>
              <input
                className="form-control"
                type="password"
                value={selfPwd}
                onChange={(e) => setSelfPwd(e.target.value)}
                placeholder="Set new password"
              />
            </div>
            <div className="col-12">
              <button className="btn btn-primary" type="submit" disabled={busy}>
                Save account
              </button>
            </div>
          </form>
        </div>
      </div>

      {isAdmin && (
        <div className="card bg-dark-subtle border-0">
          <div className="card-body">
            <h3 className="h5 mb-3">Users</h3>

            <form className="row g-3" onSubmit={addUser}>
              <div className="col-12 col-md-3">
                <label className="form-label">Username</label>
                <input
                  className="form-control"
                  value={newUser.username}
                  onChange={(e) =>
                    setNewUser((u) => ({ ...u, username: e.target.value }))
                  }
                  placeholder="username"
                  required
                />
              </div>
              <div className="col-12 col-md-3">
                <label className="form-label">Password</label>
                <input
                  className="form-control"
                  type="password"
                  value={newUser.password}
                  onChange={(e) =>
                    setNewUser((u) => ({ ...u, password: e.target.value }))
                  }
                  placeholder="Set a password"
                  required
                />
              </div>
              <div className="col-12 col-md-4">
                <label className="form-label">Display name</label>
                <input
                  className="form-control"
                  value={newUser.display_name}
                  onChange={(e) =>
                    setNewUser((u) => ({ ...u, display_name: e.target.value }))
                  }
                  placeholder="Optional"
                />
              </div>
              <div className="col-12 col-md-3">
                <label className="form-label">Roles</label>
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
                      user
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
                  Add user
                </button>
              </div>
            </form>

            <div className="table-responsive mt-4">
              <table className="table users-table table-dark table-striped align-middle mb-0 w-100">
                <thead>
                  <tr>
                    <th>User</th>
                    <th>Roles / Password</th>
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
                        <td>
                          <input
                            className="form-control mb-2"
                            value={state.new_username}
                            onChange={(e) =>
                              onEditField(
                                u.username,
                                "new_username",
                                e.target.value
                              )
                            }
                          />
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
                            placeholder="Display name"
                          />
                        </td>
                        <td>
                          <div className="users-role-group mb-2">
                            {["user", "admin"].map((r) => (
                              <div className="form-check" key={r}>
                                <input
                                  className="form-check-input"
                                  type="checkbox"
                                  checked={(state.roles || []).includes(r)}
                                  onChange={() =>
                                    onEditField(
                                      u.username,
                                      "roles",
                                      toggleRole(state, r)
                                    )
                                  }
                                  id={`${u.username}-${r}`}
                                />
                                <label className="form-check-label ms-1" htmlFor={`${u.username}-${r}`}>
                                  {r}
                                </label>
                              </div>
                            ))}
                          </div>
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
                            placeholder="Set new password"
                          />
                        </td>
                        <td className="text-end">
                          <div className="btn-group">
                            <button
                              className="btn btn-outline-primary btn-sm"
                              type="button"
                              onClick={() => saveUser(u.username)}
                              disabled={busy}
                            >
                              Save
                            </button>
                            <button
                              className="btn btn-outline-danger btn-sm"
                              type="button"
                              onClick={() => removeUser(u.username)}
                              disabled={busy}
                            >
                              Delete
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
