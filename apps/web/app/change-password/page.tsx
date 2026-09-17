"use client";

import { FormEvent, useState } from "react";
import { GsbLogo } from "@/components/Logo";
import { changePassword } from "@/lib/api";

export default function ChangePasswordPage() {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (next.length < 8) {
      setError("New password must be at least 8 characters.");
      return;
    }
    if (next !== confirm) {
      setError("New passwords do not match.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      await changePassword(current, next);
      window.location.href = "/";
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not update password");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login-wrap">
      <form className="login-card" onSubmit={onSubmit}>
        <GsbLogo height={48} />
        <h1 className="page-title" style={{ marginTop: 16 }}>Change password</h1>
        <p className="muted">Choose a new password before using the app.</p>
        <div style={{ height: 16 }} />
        <label htmlFor="current">Current password</label>
        <input id="current" type="password" autoComplete="current-password" value={current} onChange={(e) => setCurrent(e.target.value)} required />
        <div style={{ height: 12 }} />
        <label htmlFor="next">New password</label>
        <input id="next" type="password" autoComplete="new-password" minLength={8} value={next} onChange={(e) => setNext(e.target.value)} required />
        <div style={{ height: 12 }} />
        <label htmlFor="confirm">Confirm new password</label>
        <input id="confirm" type="password" autoComplete="new-password" minLength={8} value={confirm} onChange={(e) => setConfirm(e.target.value)} required />
        <div style={{ height: 16 }} />
        {error ? <div className="err">{error}</div> : null}
        {error ? <div style={{ height: 12 }} /> : null}
        <button className="btn" disabled={busy} type="submit">
          {busy ? "Saving…" : "Update password"}
        </button>
      </form>
    </div>
  );
}
