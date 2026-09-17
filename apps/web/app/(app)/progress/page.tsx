"use client";

import { FormEvent, Fragment, useEffect, useState } from "react";
import { api, getSiteId } from "@/lib/api";

type Plan = {
  id: string;
  plan_code: string;
  job_description: string;
  status: string;
  classification: string;
  equipment_tag?: string;
  equipment_id?: string | null;
  ready?: boolean;
};
type Progress = {
  id: string;
  plan_id: string;
  activity?: string;
  status: string;
  quantity: string;
  unit?: string;
  update?: string;
  has_issue?: boolean;
  issue_description?: string;
  remarks: string;
  manpower?: string;
};

function activityName(plan: Plan) {
  return plan.equipment_tag || plan.job_description || plan.plan_code;
}

function tone(status: string) {
  if (status === "Hold") return "hold";
  if (status === "Completed") return "done";
  if (status === "In progressing" || status === "Planned") return "going";
  return "idle";
}

export default function ProgressPage() {
  const [plans, setPlans] = useState<Plan[]>([]);
  const [progress, setProgress] = useState<Progress[]>([]);
  const [planId, setPlanId] = useState("");
  const [qty, setQty] = useState("");
  const [unit, setUnit] = useState("");
  const [manpower, setManpower] = useState("");
  const [update, setUpdate] = useState("");
  const [issue, setIssue] = useState("no");
  const [issueDesc, setIssueDesc] = useState("");
  const [status, setStatus] = useState("progress");
  const [remarks, setRemarks] = useState("");
  const [error, setError] = useState("");
  const [idleOpen, setIdleOpen] = useState(false);
  const [idleManpower, setIdleManpower] = useState("");
  const [idleReason, setIdleReason] = useState("");
  const [idleRemarks, setIdleRemarks] = useState("");

  function load(keepId = "") {
    const siteId = getSiteId();
    if (!siteId) return;
    Promise.all([
      api<Plan[]>(`/api/v1/sites/${siteId}/plans?open=true`),
      api<Progress[]>(`/api/v1/sites/${siteId}/progress`),
    ])
      .then(([p, pr]) => {
        setPlans(p);
        setProgress(pr);
        const openRows = p.filter((x) => x.status !== "Completed");
        setPlanId(openRows.some((x) => x.id === keepId) ? keepId : "");
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Failed"));
    api<{ manpower?: string; reason?: string; remarks?: string }>(`/api/v1/sites/${siteId}/progress/idle`)
      .then((idle) => {
        if (idle?.manpower && idle.manpower !== "0") setIdleManpower(String(idle.manpower));
        if (idle?.reason) setIdleReason(idle.reason);
        if (idle?.remarks) setIdleRemarks(idle.remarks);
      })
      .catch(() => {
        /* idle is optional */
      });
  }

  useEffect(() => {
    load();
  }, []);

  const open = plans.filter((p) => p.status !== "Completed");
  const selected = plans.find((p) => p.id === planId);
  const existing = progress.find((p) => p.plan_id === planId);

  useEffect(() => {
    if (!existing) {
      setQty("");
      setUnit("");
      setManpower("");
      setUpdate("");
      setIssue("no");
      setIssueDesc("");
      setStatus("progress");
      setRemarks("");
      return;
    }
    setQty(String(existing.quantity || ""));
    setUnit(existing.unit || "");
    setManpower(existing.manpower && existing.manpower !== "0" ? String(existing.manpower) : "");
    setUpdate(existing.update || "");
    setIssue(existing.has_issue ? "yes" : "no");
    setIssueDesc(existing.issue_description || "");
    setRemarks(existing.remarks || "");
    const plan = plans.find((p) => p.id === existing.plan_id);
    if (plan?.status === "Hold") setStatus("hold");
    else if (plan?.status === "Completed") setStatus("completed");
    else setStatus("progress");
  }, [planId, existing?.id]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    const siteId = getSiteId();
    if (!siteId || !planId) return;
    if (issue === "yes" && !issueDesc.trim()) {
      setError("Describe the issue.");
      return;
    }
    setError("");
    try {
      const body = new FormData();
      body.append("plan_id", planId);
      body.append("status", status);
      body.append("quantity", qty || "0");
      body.append("unit", unit);
      body.append("manpower", manpower || "0");
      body.append("update", update);
      body.append("has_issue", issue);
      body.append("issue_description", issueDesc);
      body.append("remarks", remarks);
      await api(`/api/v1/sites/${siteId}/progress`, { method: "POST", body });
      load(status === "completed" ? "" : planId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    }
  }

  async function saveIdle(e: FormEvent) {
    e.preventDefault();
    const siteId = getSiteId();
    if (!siteId) return;
    if (!idleManpower.trim() || !idleReason.trim()) {
      setError("Enter idle manpower and reason.");
      return;
    }
    setError("");
    try {
      const body = new FormData();
      body.append("manpower", idleManpower);
      body.append("reason", idleReason);
      body.append("remarks", idleRemarks);
      await api(`/api/v1/sites/${siteId}/progress/idle`, { method: "POST", body });
      setIdleOpen(false);
      load(planId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    }
  }

  return (
    <div className="page">
      <h2 className="page-title">Progress</h2>
      <p className="muted">Open activities stay here until they are completed. Hold stays on the list in red.</p>
      {error ? <div className="err">{error}</div> : null}

      {open.length ? (
        <div className="plan-table-wrap progress-table-wrap">
          <table className="plan-table">
            <thead>
              <tr>
                <th>Activity</th>
                <th>Status</th>
                <th>Ready</th>
              </tr>
            </thead>
            <tbody>
              {open.map((plan) => (
                <Fragment key={plan.id}>
                  <tr
                    className={plan.id === planId ? "selected-row" : ""}
                    onClick={() => setPlanId(plan.id === planId ? "" : plan.id)}
                  >
                    <td>
                      <button type="button" className={`status-dot ${tone(plan.status)}`}>
                        {activityName(plan)}
                      </button>
                    </td>
                    <td>{plan.status}</td>
                    <td className="ready-cell">{plan.ready ? "Yes" : "No"}</td>
                  </tr>
                  {selected && plan.id === planId ? (
                    <tr className="progress-form-row" onClick={(e) => e.stopPropagation()}>
                      <td colSpan={3}>
                        <form onSubmit={onSubmit}>
                          <label>Quantity</label>
                          <input inputMode="decimal" value={qty} onChange={(e) => setQty(e.target.value)} />
                          <div style={{ height: 8 }} />
                          <label>Unit</label>
                          <input value={unit} onChange={(e) => setUnit(e.target.value)} placeholder="Nos, MT, m…" />
                          <div style={{ height: 8 }} />
                          <label>Manpower allocation</label>
                          <input inputMode="numeric" value={manpower} onChange={(e) => setManpower(e.target.value)} placeholder="e.g. 5" />
                          <div style={{ height: 8 }} />
                          <label>Update</label>
                          <input value={update} onChange={(e) => setUpdate(e.target.value)} placeholder="What was updated" />
                          <div style={{ height: 8 }} />
                          <label>Was there any issue?</label>
                          <div className="row">
                            <label className="radio-line">
                              <input type="radio" name="issue" checked={issue === "yes"} onChange={() => setIssue("yes")} /> Yes
                            </label>
                            <label className="radio-line">
                              <input type="radio" name="issue" checked={issue === "no"} onChange={() => setIssue("no")} /> No
                            </label>
                          </div>
                          {issue === "yes" ? (
                            <>
                              <div style={{ height: 8 }} />
                              <label>Describe</label>
                              <textarea value={issueDesc} onChange={(e) => setIssueDesc(e.target.value)} required />
                            </>
                          ) : null}
                          <div style={{ height: 8 }} />
                          <label>Status</label>
                          <select value={status} onChange={(e) => setStatus(e.target.value)}>
                            <option value="hold">Hold</option>
                            <option value="progress">Progress</option>
                            <option value="completed">Completed</option>
                          </select>
                          <div style={{ height: 8 }} />
                          <label>Remarks</label>
                          <textarea value={remarks} onChange={(e) => setRemarks(e.target.value)} />
                          <div style={{ height: 12 }} />
                          <button className="btn" type="submit">
                            Save progress
                          </button>
                        </form>
                      </td>
                    </tr>
                  ) : null}
                </Fragment>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="muted">No open activities. Add them in Plan first.</div>
      )}
      <div style={{ height: 16 }} />
      {idleOpen ? (
        <form className="card" onSubmit={saveIdle}>
          <h3 className="page-sub" style={{ color: "inherit", fontWeight: 700 }}>Idle workers</h3>
          <p className="muted">Record manpower idle due to weather or any other reason.</p>
          <div style={{ height: 8 }} />
          <label>Manpower</label>
          <input inputMode="numeric" value={idleManpower} onChange={(e) => setIdleManpower(e.target.value)} placeholder="e.g. 8" required />
          <div style={{ height: 8 }} />
          <label>Reason</label>
          <input value={idleReason} onChange={(e) => setIdleReason(e.target.value)} placeholder="Weather, rain, no work front…" required />
          <div style={{ height: 8 }} />
          <label>Remarks</label>
          <textarea value={idleRemarks} onChange={(e) => setIdleRemarks(e.target.value)} />
          <div style={{ height: 12 }} />
          <div className="row">
            <button className="btn ghost" type="button" onClick={() => setIdleOpen(false)}>
              Cancel
            </button>
            <button className="btn" type="submit">
              Save idle workers
            </button>
          </div>
        </form>
      ) : (
        <button className="btn ghost" type="button" onClick={() => setIdleOpen(true)}>
          Idle workers
        </button>
      )}
    </div>
  );
}
