"use client";

import { useEffect, useState } from "react";
import { api, getSiteId, getToken, me } from "@/lib/api";

type Row = {
  id: string;
  po_ref: string;
  equipment_tag: string;
  description: string;
  unit: string;
  po_quantity: string | number;
  completed_quantity: string | number;
  remaining_quantity: string | number;
  status: string;
  erection_front_status: string;
  remarks: string;
  photo_ref: string;
};

const API = process.env.NEXT_PUBLIC_API_URL || "";

export default function MasterPage() {
  const [rows, setRows] = useState<Row[]>([]);
  const [role, setRole] = useState("");
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const [busy, setBusy] = useState(false);

  function load() {
    const siteId = getSiteId();
    if (!siteId) return;
    api<Row[]>(`/api/v1/sites/${siteId}/master`)
      .then(setRows)
      .catch((e) => setError(e instanceof Error ? e.message : "Failed"));
  }

  useEffect(() => {
    me().then((u) => setRole(u.global_role));
    load();
  }, []);

  async function downloadTemplate() {
    const siteId = getSiteId();
    if (!siteId) return;
    const res = await fetch(`${API}/api/v1/sites/${siteId}/master/template`, {
      headers: { Authorization: `Bearer ${getToken() || ""}` },
      credentials: "include",
    });
    if (!res.ok) {
      setError("Could not download template");
      return;
    }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "GSB-master-list.xlsx";
    a.click();
    URL.revokeObjectURL(url);
  }

  async function onFile(file: File) {
    const siteId = getSiteId();
    if (!siteId) return;
    setBusy(true);
    setError("");
    setOk("");
    try {
      const body = new FormData();
      body.append("file", file);
      const result = await api<{ created: number; updated: number; total: number }>(
        `/api/v1/sites/${siteId}/master/import`,
        { method: "POST", body },
      );
      setOk(`Imported ${result.total} rows (${result.created} new, ${result.updated} updated).`);
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Import failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="page">
      <h2 className="page-title">Master list (this project)</h2>
      <p className="muted">PO jobs only. Progress updates quantity, status, remarks, and photos.</p>
      {role === "OWNER" ? (
        <div className="card">
          <button className="btn secondary" type="button" onClick={downloadTemplate}>
            Download Excel template
          </button>
          <div style={{ height: 10 }} />
          <label>Upload Excel</label>
          <input
            type="file"
            accept=".xlsx,.xlsm"
            disabled={busy}
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) onFile(file);
            }}
          />
        </div>
      ) : (
        <div className="muted">Owner uploads the Excel master. You can view this project only.</div>
      )}
      {error ? <div className="err">{error}</div> : null}
      {ok ? <div className="okmsg">{ok}</div> : null}
      {rows.map((r) => (
        <div className="emp" key={r.id}>
          <h3>{r.po_ref} · {r.equipment_tag}</h3>
          <div className="muted">
            {r.description}<br />
            Qty {r.completed_quantity}/{r.po_quantity} {r.unit} · remaining {r.remaining_quantity}
            <br />
            Status: {r.status || "—"}
            <br />
            Front: {r.erection_front_status || "—"}
            <br />
            Remarks: {r.remarks || "—"}
          </div>
          {r.photo_ref ? (
            <a href={r.photo_ref} target="_blank" rel="noreferrer">
              Latest photo
            </a>
          ) : null}
        </div>
      ))}
    </div>
  );
}
