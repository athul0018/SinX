"use client";

import { useEffect, useState } from "react";
import { api, getSiteId } from "@/lib/api";

type Row = {
  id: string;
  activity?: string;
  plan_status?: string;
  quantity?: string | number;
  unit?: string;
  manpower?: string;
  update?: string;
  remarks?: string;
  kind?: string;
  reason?: string;
};

export default function TodayProgressPage() {
  const [rows, setRows] = useState<Row[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    const siteId = getSiteId();
    if (!siteId) return;
    api<Row[]>(`/api/v1/sites/${siteId}/progress/today`)
      .then(setRows)
      .catch((e) => setError(e instanceof Error ? e.message : "Failed"));
  }, []);

  return (
    <div className="page">
      <h2 className="page-title">Today&apos;s Progress</h2>
      <p className="muted">Updates saved today for work that is still open. Completed work leaves this list.</p>
      {error ? <div className="err">{error}</div> : null}
      {rows.length ? (
        <div className="plan-table-wrap progress-table-wrap">
          <table className="plan-table">
            <thead>
              <tr>
                <th>Activity</th>
                <th>Status</th>
                <th>Manpower</th>
                <th>Quantity</th>
                <th>Reason</th>
                <th>Update</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id}>
                  <td>
                    <strong>{row.activity || row.id}</strong>
                  </td>
                  <td>{row.plan_status || "In progressing"}</td>
                  <td>{row.manpower && row.manpower !== "0" ? row.manpower : "—"}</td>
                  <td>
                    {row.kind === "idle" ? "—" : `${row.quantity || "0"}${row.unit ? ` ${row.unit}` : ""}`}
                  </td>
                  <td>{row.kind === "idle" ? row.reason || row.update || "—" : "—"}</td>
                  <td>{row.kind === "idle" ? row.remarks || "—" : row.update || row.remarks || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="muted">No progress saved for today yet. Update an activity in Progress.</p>
      )}
    </div>
  );
}
