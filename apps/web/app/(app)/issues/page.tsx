"use client";

import { FormEvent, useEffect, useState } from "react";
import { api, getSiteId } from "@/lib/api";

type Comment = { text: string; at?: string };

type Issue = {
  id: string;
  plan_id: string;
  activity?: string;
  issue_description?: string;
  observed_at?: string;
  rectify_status?: string;
  rectify_status_at?: string;
  comments?: Comment[];
};

export default function IssuesPage() {
  const [items, setItems] = useState<Issue[]>([]);
  const [error, setError] = useState("");
  const [drafts, setDrafts] = useState<Record<string, { observed_at: string; status: string; comment: string }>>({});
  const [busy, setBusy] = useState("");

  function load() {
    const siteId = getSiteId();
    if (!siteId) return;
    api<Issue[]>(`/api/v1/sites/${siteId}/issues`)
      .then((rows) => {
        setItems(rows);
        const next: Record<string, { observed_at: string; status: string; comment: string }> = {};
        for (const row of rows) {
          next[row.id] = {
            observed_at: row.observed_at || "",
            status: row.rectify_status || "Raised",
            comment: "",
          };
        }
        setDrafts(next);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Failed"));
  }

  useEffect(() => {
    load();
  }, []);

  function patchDraft(id: string, fields: Partial<{ observed_at: string; status: string; comment: string }>) {
    setDrafts((prev) => ({ ...prev, [id]: { ...prev[id], ...fields } }));
  }

  async function saveIssue(id: string, e: FormEvent) {
    e.preventDefault();
    const siteId = getSiteId();
    const draft = drafts[id];
    if (!siteId || !draft) return;
    setError("");
    setBusy(id);
    try {
      const updated = await api<Issue>(`/api/v1/sites/${siteId}/issues/${id}`, {
        method: "PATCH",
        body: JSON.stringify({
          observed_at: draft.observed_at || null,
          rectify_status: draft.status,
          comment: draft.comment.trim() || null,
        }),
      });
      if (updated.rectify_status === "Closed") {
        setItems((rows) => rows.filter((row) => row.id !== id));
      } else {
        setItems((rows) => rows.map((row) => (row.id === id ? updated : row)));
        patchDraft(id, { comment: "", observed_at: updated.observed_at || "", status: updated.rectify_status || "Raised" });
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setBusy("");
    }
  }

  return (
    <div className="page">
      <h2 className="page-title">Issues</h2>
      <p className="muted">Open issues from Progress. Closed issues leave this list.</p>
      {error ? <div className="err">{error}</div> : null}
      {items.length ? (
        items.map((item) => {
          const draft = drafts[item.id] || { observed_at: "", status: "Raised", comment: "" };
          return (
            <form className="card" key={item.id} onSubmit={(e) => saveIssue(item.id, e)}>
              <h3 className="page-title" style={{ fontSize: 16 }}>
                {item.activity || item.plan_id}
              </h3>
              <p>{item.issue_description}</p>
              <div style={{ height: 8 }} />
              <label>Observed at</label>
              <input
                type="date"
                value={draft.observed_at}
                onChange={(e) => patchDraft(item.id, { observed_at: e.target.value })}
              />
              <div style={{ height: 8 }} />
              <label>The issue is with you to rectify</label>
              <select value={draft.status} onChange={(e) => patchDraft(item.id, { status: e.target.value })}>
                <option value="Raised">Raised</option>
                <option value="Closed">Closed</option>
              </select>
              {item.rectify_status_at ? (
                <p className="muted" style={{ marginTop: 6 }}>
                  Status date: {item.rectify_status_at}
                </p>
              ) : null}
              <div style={{ height: 8 }} />
              <label>Comment</label>
              <textarea
                value={draft.comment}
                onChange={(e) => patchDraft(item.id, { comment: e.target.value })}
                placeholder="Add a comment"
              />
              {(item.comments || []).length ? (
                <div style={{ marginTop: 10 }}>
                  <div className="muted" style={{ marginBottom: 6 }}>
                    Comments
                  </div>
                  {(item.comments || []).map((comment, index) => (
                    <div className="emp" key={`${item.id}-${index}`}>
                      <div>{comment.text}</div>
                      {comment.at ? <div className="muted">{comment.at}</div> : null}
                    </div>
                  ))}
                </div>
              ) : null}
              <div style={{ height: 12 }} />
              <button className="btn" disabled={busy === item.id} type="submit">
                {busy === item.id ? "Saving…" : "Save"}
              </button>
            </form>
          );
        })
      ) : (
        <p className="muted">No open issues.</p>
      )}
    </div>
  );
}
