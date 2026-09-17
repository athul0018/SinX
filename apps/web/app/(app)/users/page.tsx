"use client";

import { FormEvent, useEffect, useState } from "react";
import { Site, User, api, me } from "@/lib/api";

export default function UsersPage() {
  const [users, setUsers] = useState<User[]>([]);
  const [sites, setSites] = useState<Site[]>([]);
  const [form, setForm] = useState({
    name: "",
    email: "",
    password: "",
    global_role: "AUTHORIZED",
    site_ids: [] as string[],
  });
  const [error, setError] = useState("");

  function load() {
    Promise.all([api<User[]>("/api/v1/users"), api<Site[]>("/api/v1/sites")])
      .then(([u, s]) => {
        setUsers(u);
        setSites(s);
      })
      .catch((e) => setError(e.message));
  }

  useEffect(() => {
    me().then((u) => {
      if (u.global_role !== "OWNER") window.location.href = "/";
      else load();
    });
  }, []);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    try {
      await api("/api/v1/users", { method: "POST", body: JSON.stringify(form) });
      setForm({ name: "", email: "", password: "", global_role: "AUTHORIZED", site_ids: [] });
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    }
  }

  return (
    <div className="page">
      <h2 className="page-title">Users</h2>
      <form className="card" onSubmit={onSubmit}>
        <label>Name</label>
        <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
        <div style={{ height: 8 }} />
        <label>Email</label>
        <input type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} required />
        <div style={{ height: 8 }} />
        <label>Password</label>
        <input type="password" minLength={8} value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} required />
        <div style={{ height: 8 }} />
        <label>Role</label>
        <select value={form.global_role} onChange={(e) => setForm({ ...form, global_role: e.target.value })}>
          <option value="AUTHORIZED">AUTHORIZED</option>
          <option value="OWNER">OWNER</option>
        </select>
        <div style={{ height: 8 }} />
        <label>Assign projects</label>
        {sites.map((s) => (
          <label key={s.id} style={{ color: "var(--ink)", marginBottom: 4 }}>
            <input
              type="checkbox"
              checked={form.site_ids.includes(s.id)}
              onChange={(e) => {
                setForm({
                  ...form,
                  site_ids: e.target.checked
                    ? [...form.site_ids, s.id]
                    : form.site_ids.filter((id) => id !== s.id),
                });
              }}
            />{" "}
            {s.name}
          </label>
        ))}
        <div style={{ height: 12 }} />
        <button className="btn" type="submit">Add user</button>
      </form>
      {error ? <div className="err">{error}</div> : null}
      {users.map((u) => (
        <div className="emp" key={u.id}>
          <h3>{u.name}</h3>
          <div className="muted">
            {u.email} · {u.global_role} · {u.is_active ? "Active" : "Inactive"}
            <br />
            {u.sites.map((s) => s.code).join(", ") || "No project assignment"}
          </div>
          {u.is_active ? (
            <button
              className="btn bad"
              type="button"
              onClick={async () => {
                if (!window.confirm(`Deactivate ${u.name}?`)) return;
                await api(`/api/v1/users/${u.id}/deactivate`, { method: "POST" });
                load();
              }}
            >
              Deactivate
            </button>
          ) : (
            <button
              className="btn secondary"
              type="button"
              onClick={async () => {
                await api(`/api/v1/users/${u.id}/reactivate`, { method: "POST" });
                load();
              }}
            >
              Reactivate
            </button>
          )}
        </div>
      ))}
    </div>
  );
}
