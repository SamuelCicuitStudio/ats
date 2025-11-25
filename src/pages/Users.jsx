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
    if (isAdmin && token) {
      loadUsers();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
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
      setNewUser({ username: "", password: "", display_name: "", roles: ["user"] });
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
      // if current user was updated, refresh their profile
      if (currentUser?.username === username) {
        onUserUpdate?.(updated);
      }
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
    <div className="panel">
      <div className="panel">
        <h3>Your account</h3>
        <form className="auth-form" onSubmit={saveSelf}>
          <label className="uplabel">Display name</label>
          <input
            value={selfName}
            onChange={(e) => setSelfName(e.target.value)}
            placeholder="Your name"
          />

          <label className="uplabel">New password</label>
          <input
            type="password"
            value={selfPwd}
            onChange={(e) => setSelfPwd(e.target.value)}
            placeholder="••••••••"
          />

          <button className="primary" type="submit" disabled={busy}>
            Save account
          </button>
        </form>
      </div>

      {isAdmin && (
        <div className="panel">
          <h3>Users</h3>

          <form className="auth-form" onSubmit={addUser}>
            <label className="uplabel">Username</label>
            <input
              value={newUser.username}
              onChange={(e) =>
                setNewUser((u) => ({ ...u, username: e.target.value }))
              }
              placeholder="username"
              required
            />

            <label className="uplabel">Password</label>
            <input
              type="password"
              value={newUser.password}
              onChange={(e) =>
                setNewUser((u) => ({ ...u, password: e.target.value }))
              }
              placeholder="Set a password"
              required
            />

            <label className="uplabel">Display name</label>
            <input
              value={newUser.display_name}
              onChange={(e) =>
                setNewUser((u) => ({ ...u, display_name: e.target.value }))
              }
              placeholder="Optional"
            />

            <div className="chiprow">
              <label>
                <input
                  type="checkbox"
                  checked={newUser.roles.includes("user")}
                  onChange={() =>
                    setNewUser((u) => ({
                      ...u,
                      roles: toggleRole(u, "user"),
                    }))
                  }
                />{" "}
                user
              </label>
              <label>
                <input
                  type="checkbox"
                  checked={newUser.roles.includes("admin")}
                  onChange={() =>
                    setNewUser((u) => ({
                      ...u,
                      roles: toggleRole(u, "admin"),
                    }))
                  }
                />{" "}
                admin
              </label>
            </div>

            <button className="primary" type="submit" disabled={busy}>
              Add user
            </button>
          </form>

          <div className="table">
            <div className="table-head">
              <span>User</span>
              <span>Roles</span>
              <span>Actions</span>
            </div>
            {users.map((u) => {
              const state = editing[u.username] || {
                new_username: u.username,
                display_name: u.display_name,
                roles: u.roles,
                password: "",
              };
              return (
                <div className="table-row" key={u.username}>
                  <div className="table-cell">
                    <input
                      value={state.new_username}
                      onChange={(e) =>
                        onEditField(u.username, "new_username", e.target.value)
                      }
                    />
                    <input
                      value={state.display_name || ""}
                      onChange={(e) =>
                        onEditField(u.username, "display_name", e.target.value)
                      }
                      placeholder="Display name"
                    />
                  </div>
                  <div className="table-cell">
                    <div className="chiprow">
                      {["user", "admin"].map((r) => (
                        <label key={r}>
                          <input
                            type="checkbox"
                            checked={(state.roles || []).includes(r)}
                            onChange={() =>
                              onEditField(u.username, "roles", toggleRole(state, r))
                            }
                          />{" "}
                          {r}
                        </label>
                      ))}
                    </div>
                    <input
                      type="password"
                      value={state.password || ""}
                      onChange={(e) =>
                        onEditField(u.username, "password", e.target.value)
                      }
                      placeholder="Set new password"
                    />
                  </div>
                  <div className="table-cell actions">
                    <button
                      className="primary ghost"
                      type="button"
                      onClick={() => saveUser(u.username)}
                      disabled={busy}
                    >
                      Save
                    </button>
                    <button
                      className="danger ghost"
                      type="button"
                      onClick={() => removeUser(u.username)}
                      disabled={busy}
                    >
                      Delete
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {err && <div className="error">{err}</div>}
    </div>
  );
}
