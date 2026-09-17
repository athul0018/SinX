"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, getSiteId } from "@/lib/api";

type Equipment = { id: string; po_ref: string; equipment_tag: string; description: string };

type DraftRow = {
  key: string;
  classification: string;
  equipment_id: string;
  job_description: string;
  ready: boolean;
  requirement: string;
  comment: string;
};

function activityLabel(item: Equipment) {
  const tag = item.equipment_tag || item.description || "Untitled";
  return item.po_ref ? `${item.po_ref} · ${tag}` : tag;
}

function emptyRow(): DraftRow {
  return {
    key: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    classification: "Under PO",
    equipment_id: "",
    job_description: "",
    ready: false,
    requirement: "",
    comment: "",
  };
}

export default function PlansPage() {
  const router = useRouter();
  const [master, setMaster] = useState<Equipment[]>([]);
  const [rows, setRows] = useState<DraftRow[]>([emptyRow()]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const siteId = getSiteId();
    if (!siteId) return;
    api<Equipment[]>(`/api/v1/sites/${siteId}/equipment`)
      .then(setMaster)
      .catch((e) => setError(e instanceof Error ? e.message : "Failed"));
  }, []);

  function patch(key: string, fields: Partial<DraftRow>) {
    setRows((list) => list.map((row) => (row.key === key ? { ...row, ...fields } : row)));
  }

  function rowReady(row: DraftRow) {
    if (row.classification === "Under PO") return Boolean(row.equipment_id);
    return Boolean(row.job_description.trim());
  }

  function payload(row: DraftRow) {
    return {
      classification: row.classification,
      equipment_id: row.classification === "Under PO" && row.equipment_id ? row.equipment_id : null,
      job_description: row.job_description,
      status: "Not started",
      ready: row.ready,
      requirement: row.requirement,
      comment: row.comment,
    };
  }

  async function saveAll() {
    const siteId = getSiteId();
    if (!siteId) return;
    const readyRows = rows.filter(rowReady);
    if (!readyRows.length) {
      setError("Select or enter at least one activity before saving.");
      return;
    }
    setError("");
    setBusy(true);
    try {
      for (const row of readyRows) {
        await api(`/api/v1/sites/${siteId}/plans`, {
          method: "POST",
          body: JSON.stringify(payload(row)),
        });
      }
      setRows([emptyRow()]);
      router.push("/progress");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="page">
      <h2 className="page-title">Plan</h2>
      <p className="muted">Enter activities, then Save. They move to Progress and this form clears.</p>
      {error ? <div className="err">{error}</div> : null}
      <div className="plan-table-wrap">
        <table className="plan-table">
          <thead>
            <tr>
              <th>Category</th>
              <th>Activity</th>
              <th>Ready</th>
              <th>Requirement</th>
              <th>Comment</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.key} className="plan-draft">
                <td>
                  <select
                    value={row.classification}
                    onChange={(e) =>
                      patch(row.key, { classification: e.target.value, equipment_id: "", job_description: "" })
                    }
                  >
                    <option>Under PO</option>
                    <option>Not Under PO</option>
                  </select>
                </td>
                <td>
                  {row.classification === "Under PO" ? (
                    <select
                      value={row.equipment_id}
                      onChange={(e) => patch(row.key, { equipment_id: e.target.value })}
                    >
                      <option value="">Select activity</option>
                      {master.map((item) => (
                        <option key={item.id} value={item.id}>
                          {activityLabel(item)}
                        </option>
                      ))}
                    </select>
                  ) : (
                    <input
                      value={row.job_description}
                      onChange={(e) => patch(row.key, { job_description: e.target.value })}
                      placeholder="Activity name"
                    />
                  )}
                </td>
                <td className="ready-cell">
                  <input
                    type="checkbox"
                    checked={row.ready}
                    onChange={(e) => patch(row.key, { ready: e.target.checked })}
                  />
                </td>
                <td>
                  <input
                    value={row.requirement}
                    onChange={(e) => patch(row.key, { requirement: e.target.value })}
                    placeholder="Hydra, crane…"
                  />
                </td>
                <td>
                  <input
                    value={row.comment}
                    onChange={(e) => patch(row.key, { comment: e.target.value })}
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
        <button className="btn ghost" disabled={busy} type="button" onClick={() => setRows((list) => [...list, emptyRow()])}>
          Add plan row
        </button>
        <button className="btn" disabled={busy} type="button" onClick={saveAll}>
          {busy ? "Saving…" : "Save"}
        </button>
      </div>
    </div>
  );
}
