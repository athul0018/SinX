"use client";

import { FormEvent, useEffect, useState } from "react";
import { Site, api, me } from "@/lib/api";

export default function SitesPage() {
  const [sites, setSites] = useState<Site[]>([]);
  const [name, setName] = useState("");
  const [code, setCode] = useState("");
  const [error, setError] = useState("");

  function load() {
    api<Site[]>("/api/v1/sites").then(setSites).catch((e) => setError(e.message));
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
      await api("/api/v1/sites", { method: "POST", body: JSON.stringify({ name, code }) });
      setName("");
      setCode("");
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    }
  }

  return (
    <div className="page">
      <h2 className="page-title">Projects</h2>
      <form className="card" onSubmit={onSubmit}>
        <label>Name</label>
        <input value={name} onChange={(e) => setName(e.target.value)} required />
        <div style={{ height: 8 }} />
        <label>Code</label>
        <input value={code} onChange={(e) => setCode(e.target.value)} required />
        <div style={{ height: 12 }} />
        <button className="btn" type="submit">Add project</button>
      </form>
      {error ? <div className="err">{error}</div> : null}
      {sites.map((s) => (
        <div className="emp" key={s.id}>
          <h3>{s.name}</h3>
          <div className="muted">{s.code} · {s.status}</div>
          <button
            className="btn secondary"
            type="button"
            onClick={async () => {
              const next = s.status === "active" ? "inactive" : "active";
              await api(`/api/v1/sites/${s.id}`, {
                method: "PATCH",
                body: JSON.stringify({ status: next }),
              });
              load();
            }}
          >
            {s.status === "active" ? "Disable project" : "Enable project"}
          </button>
        </div>
      ))}
    </div>
  );
}
