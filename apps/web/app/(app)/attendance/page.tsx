"use client";

import { useEffect, useState } from "react";
import { api, getSiteId } from "@/lib/api";

type Row = {
  employee_id: string;
  employee_code: string;
  name: string;
  designation: string;
  morning_status: string | null;
  evening_type: string | null;
  ot_hours: string | number;
};

export default function AttendancePage() {
  const [rows, setRows] = useState<Row[]>([]);
  const [morning, setMorning] = useState<Record<string, string>>({});
  const [types, setTypes] = useState<Record<string, string>>({});
  const [ot, setOt] = useState<Record<string, string>>({});
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const [busy, setBusy] = useState("");
  const [morningDone, setMorningDone] = useState(false);
  const [eveningDone, setEveningDone] = useState(false);

  function load() {
    const siteId = getSiteId();
    if (!siteId) return;
    api<Row[]>(`/api/v1/sites/${siteId}/attendance`)
      .then((data) => {
        setRows(data);
        const m: Record<string, string> = {};
        const t: Record<string, string> = {};
        const o: Record<string, string> = {};
        let allMorning = data.length > 0;
        const presentRows = data.filter((r) => r.morning_status === "Present");
        data.forEach((r) => {
          if (r.morning_status) m[r.employee_id] = r.morning_status;
          else allMorning = false;
          if (r.morning_status === "Present") {
            t[r.employee_id] = r.evening_type || "full_day";
            o[r.employee_id] = String(r.ot_hours ?? "0");
          }
        });
        if (!data.length) allMorning = false;
        const allEvening =
          allMorning &&
          (presentRows.length === 0 || presentRows.every((r) => Boolean(r.evening_type)));
        setMorning(m);
        setTypes(t);
        setOt(o);
        setMorningDone(allMorning);
        setEveningDone(allEvening);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Failed"));
  }

  useEffect(() => {
    load();
  }, []);

  const unmarked = rows.filter((r) => !morning[r.employee_id]);
  const present = rows.filter((r) => r.morning_status === "Present");

  async function saveMorning() {
    const siteId = getSiteId();
    if (!siteId) return;
    if (unmarked.length) {
      setError("Mark P or A for every employee.");
      return;
    }
    setBusy("morning");
    setError("");
    setOk("");
    try {
      await api(`/api/v1/sites/${siteId}/attendance/morning`, {
        method: "POST",
        body: JSON.stringify({
          answers: rows.map((r) => ({
            employee_id: r.employee_id,
            status: morning[r.employee_id],
          })),
        }),
      });
      setOk("Morning saved. Confirm evening for Present staff.");
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Save failed");
    } finally {
      setBusy("");
    }
  }

  async function saveEvening() {
    const siteId = getSiteId();
    if (!siteId) return;
    if (!present.length) {
      setError("No Present staff for evening confirmation.");
      return;
    }
    if (!window.confirm("Confirm evening attendance (F / H and OT)?")) return;
    setBusy("evening");
    setError("");
    setOk("");
    try {
      await api(`/api/v1/sites/${siteId}/attendance/evening`, {
        method: "POST",
        body: JSON.stringify({
          answers: present.map((r) => ({
            employee_id: r.employee_id,
            evening_type: types[r.employee_id] || "full_day",
            ot_hours: Number(ot[r.employee_id] || 0),
          })),
        }),
      });
      setOk("Attendance has been marked for today.");
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Save failed");
    } finally {
      setBusy("");
    }
  }

  return (
    <div className="page">
      <h2 className="page-title">Attendance</h2>
      {error ? <div className="err">{error}</div> : null}
      {ok ? <div className="okmsg">{ok}</div> : null}

      {!morningDone ? (
        <>
          <p className="muted">Morning: mark P (Present) or A (Absent) on the same line, then save.</p>
          <div className="plan-table-wrap progress-table-wrap">
            <table className="plan-table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>P / A</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.employee_id}>
                    <td>
                      <strong>{r.name}</strong>
                      <div className="muted">
                        {r.employee_code} · {r.designation}
                      </div>
                    </td>
                    <td>
                      <div className="row" style={{ gap: 6 }}>
                        <button
                          type="button"
                          className={`btn ${morning[r.employee_id] === "Present" ? "ok" : "secondary"}`}
                          onClick={() => setMorning({ ...morning, [r.employee_id]: "Present" })}
                        >
                          P
                        </button>
                        <button
                          type="button"
                          className={`btn ${morning[r.employee_id] === "Absent" ? "bad" : "secondary"}`}
                          onClick={() => setMorning({ ...morning, [r.employee_id]: "Absent" })}
                        >
                          A
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {rows.length === 0 ? <div className="muted">No active employees on this project.</div> : null}
          <button className="btn accent" disabled={busy === "morning" || rows.length === 0} onClick={saveMorning} style={{ marginTop: 12 }}>
            {busy === "morning" ? "Saving…" : "Save morning"}
          </button>
        </>
      ) : eveningDone ? (
        <div className="card">
          <h3 className="page-title" style={{ fontSize: 16 }}>
            Attendance has been marked for today
          </h3>
          <p className="muted">Morning and evening attendance are complete for this project.</p>
        </div>
      ) : (
        <>
          <p className="muted">Evening: Present staff only. F = Full day, H = Half day. Enter OT, then confirm.</p>
          {present.length ? (
            <>
              <div className="plan-table-wrap progress-table-wrap">
                <table className="plan-table">
                  <thead>
                    <tr>
                      <th>Name</th>
                      <th>Day</th>
                      <th>OT</th>
                    </tr>
                  </thead>
                  <tbody>
                    {present.map((r) => (
                      <tr key={r.employee_id}>
                        <td>
                          <strong>{r.name}</strong>
                          <div className="muted">{r.employee_code}</div>
                        </td>
                        <td>
                          <div className="row" style={{ gap: 6 }}>
                            <button
                              type="button"
                              className={`btn ${types[r.employee_id] === "full_day" ? "ok" : "secondary"}`}
                              onClick={() => setTypes({ ...types, [r.employee_id]: "full_day" })}
                            >
                              F
                            </button>
                            <button
                              type="button"
                              className={`btn ${types[r.employee_id] === "half_day" ? "accent" : "secondary"}`}
                              onClick={() => setTypes({ ...types, [r.employee_id]: "half_day" })}
                            >
                              H
                            </button>
                          </div>
                        </td>
                        <td>
                          <input
                            inputMode="decimal"
                            min={0}
                            max={24}
                            value={ot[r.employee_id] ?? "0"}
                            onChange={(e) => setOt({ ...ot, [r.employee_id]: e.target.value })}
                            style={{ width: 72, minHeight: 40 }}
                            aria-label={`OT hours for ${r.name}`}
                          />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <button className="btn accent" disabled={busy === "evening"} onClick={saveEvening} style={{ marginTop: 12 }}>
                {busy === "evening" ? "Saving…" : "Confirm evening"}
              </button>
            </>
          ) : (
            <div className="muted">Everyone was Absent this morning. No evening confirmation needed.</div>
          )}
        </>
      )}
    </div>
  );
}
