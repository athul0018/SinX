"use client";

import { FormEvent, useEffect, useState } from "react";
import { Site, api, getSiteId } from "@/lib/api";

type Employee = {
  id: string;
  employee_code: string;
  name: string;
  designation: string;
  status: string;
  joining_date: string;
};

export default function EmployeesPage() {
  const [rows, setRows] = useState<Employee[]>([]);
  const [sites, setSites] = useState<Site[]>([]);
  const [dest, setDest] = useState<Record<string, string>>({});
  const [error, setError] = useState("");
  const [editing, setEditing] = useState<Employee | null>(null);
  const [form, setForm] = useState({
    employee_code: "",
    name: "",
    designation: "",
    joining_date: "",
  });

  function load() {
    const siteId = getSiteId();
    if (!siteId) return;
    Promise.all([
      api<Employee[]>(`/api/v1/sites/${siteId}/employees`),
      api<Site[]>("/api/v1/sites/transfer-targets"),
    ])
      .then(([employees, allSites]) => {
        setRows(employees);
        setSites(allSites.filter((s) => s.id !== siteId));
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Failed"));
  }

  useEffect(() => {
    load();
  }, []);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    const siteId = getSiteId();
    if (!siteId) return;
    setError("");
    try {
      if (editing) {
        await api(`/api/v1/sites/${siteId}/employees/${editing.id}`, {
          method: "PATCH",
          body: JSON.stringify(form),
        });
      } else {
        await api(`/api/v1/sites/${siteId}/employees`, {
          method: "POST",
          body: JSON.stringify(form),
        });
      }
      setEditing(null);
      setForm({ employee_code: "", name: "", designation: "", joining_date: "" });
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    }
  }

  return (
    <div className="page">
      <h2 className="page-title">{editing ? "Edit employee" : "Add employee"}</h2>
      <form className="card" onSubmit={onSubmit}>
        <label>Employee ID</label>
        <input value={form.employee_code} onChange={(e) => setForm({ ...form, employee_code: e.target.value })} required />
        <div style={{ height: 8 }} />
        <label>Name</label>
        <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
        <div style={{ height: 8 }} />
        <label>Designation</label>
        <input value={form.designation} onChange={(e) => setForm({ ...form, designation: e.target.value })} required />
        <div style={{ height: 8 }} />
        <label>Joining date</label>
        <input type="date" value={form.joining_date} onChange={(e) => setForm({ ...form, joining_date: e.target.value })} required />
        <div style={{ height: 12 }} />
        <button className="btn" type="submit">{editing ? "Save changes" : "Add employee"}</button>
        {editing ? (
          <button
            className="btn secondary"
            type="button"
            style={{ marginTop: 8 }}
            onClick={() => {
              setEditing(null);
              setForm({ employee_code: "", name: "", designation: "", joining_date: "" });
            }}
          >
            Cancel edit
          </button>
        ) : null}
      </form>
      {error ? <div className="err">{error}</div> : null}
      {rows.map((r) => (
        <div className="emp" key={r.id}>
          <div>
            <h3>{r.name}</h3>
            <div className="muted">{r.employee_code} · {r.designation} · {r.status}</div>
          </div>
          <div className="row">
            <button
              className="btn secondary"
              type="button"
              onClick={() => {
                setEditing(r);
                setForm({
                  employee_code: r.employee_code,
                  name: r.name,
                  designation: r.designation,
                  joining_date: r.joining_date,
                });
              }}
            >
              Edit
            </button>
            {r.status === "Active" ? (
              <button
                className="btn bad"
                type="button"
                onClick={async () => {
                  const siteId = getSiteId();
                  if (!siteId) return;
                  if (!window.confirm(`Deactivate ${r.name}? Historical attendance is kept.`)) return;
                  await api(`/api/v1/sites/${siteId}/employees/${r.id}/deactivate`, { method: "POST" });
                  load();
                }}
              >
                Deactivate
              </button>
            ) : null}
          </div>
          {r.status === "Active" && sites.length > 0 ? (
            <div className="row">
              <select
                value={dest[r.id] || sites[0].id}
                onChange={(e) => setDest({ ...dest, [r.id]: e.target.value })}
              >
                {sites.map((s) => (
                  <option key={s.id} value={s.id}>{s.name}</option>
                ))}
              </select>
              <button
                className="btn accent"
                type="button"
                onClick={async () => {
                  const siteId = getSiteId();
                  if (!siteId) return;
                  const target = sites.find((s) => s.id === (dest[r.id] || sites[0].id));
                  if (!window.confirm(`Transfer ${r.name} to ${target?.name || "the selected project"}?`)) return;
                  await api(`/api/v1/sites/${siteId}/employees/${r.id}/transfer`, {
                    method: "POST",
                    body: JSON.stringify({ to_site_id: dest[r.id] || sites[0].id }),
                  });
                  load();
                }}
              >
                Transfer
              </button>
            </div>
          ) : null}
        </div>
      ))}
    </div>
  );
}
