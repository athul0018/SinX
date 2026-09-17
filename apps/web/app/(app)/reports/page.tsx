"use client";

import { downloadExcel, getSiteId, me, setSiteId } from "@/lib/api";
import { useEffect, useState } from "react";
import { Site } from "@/lib/api";

function currentMonth() {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
}

export default function ReportsPage() {
  const [month, setMonth] = useState(currentMonth);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");
  const [sites, setSites] = useState<Site[]>([]);
  const [siteId, setLocalSite] = useState(getSiteId() || "");

  useEffect(() => {
    me().then((user) => {
      if (user.global_role !== "OWNER") window.location.href = "/";
      else {
        setSites(user.sites);
        const current = getSiteId();
        const match = user.sites.find((s) => s.id === current) || user.sites[0];
        if (match) {
          setLocalSite(match.id);
          setSiteId(match.id);
        }
      }
    });
  }, []);

  async function download(kind: "attendance" | "progress") {
    const [year, mon] = month.split("-");
    const selected = siteId || getSiteId();
    if (!selected) return;
    setBusy(kind);
    setError("");
    try {
      const name = kind === "attendance" ? "attendance" : "progress";
      await downloadExcel(
        `/api/v1/sites/${selected}/reports/${kind}?year=${year}&month=${Number(mon)}`,
        `${name}-${year}-${mon}.xlsx`,
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Download failed");
    } finally {
      setBusy("");
    }
  }

  return (
    <div className="page">
      <h2 className="page-title">Monthly reports</h2>
      <p className="muted">Owner only. Files are for the selected project.</p>
      <div className="card">
        <label>Project</label>
        <select
          value={siteId}
          onChange={(e) => {
            setLocalSite(e.target.value);
            setSiteId(e.target.value);
          }}
        >
          {sites.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name} ({s.code})
            </option>
          ))}
        </select>
        <div style={{ height: 8 }} />
        <label>Month</label>
        <input type="month" value={month} onChange={(e) => setMonth(e.target.value)} />
      </div>
      {error ? <div className="err">{error}</div> : null}
      <button className="btn" disabled={!!busy} type="button" onClick={() => download("attendance")}>
        {busy === "attendance" ? "Preparing…" : "Download attendance sheet"}
      </button>
      <button className="btn accent" disabled={!!busy} type="button" onClick={() => download("progress")}>
        {busy === "progress" ? "Preparing…" : "Download monthly progress"}
      </button>
      <div className="muted">
        Attendance: EMP.ID, name, designation, then each day has weekday + OT columns (F = full day, H = half day, A = absent).
        Progress: progress records, PO master list, and non-PO jobs.
      </div>
    </div>
  );
}
