"use client";

import { FormEvent, useState } from "react";
import { GsbLogo } from "@/components/Logo";
import { getSiteId, login, setSiteId } from "@/lib/api";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const result = await login(email, password);
      const saved = getSiteId();
      const match = result.user.sites.find((s) => s.id === saved);
      if (match) setSiteId(match.id);
      else if (result.user.sites[0]) setSiteId(result.user.sites[0].id);
      window.location.href = result.user.must_change_password ? "/change-password" : "/";
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login-wrap">
      <form className="login-card" onSubmit={onSubmit}>
        <GsbLogo height={48} />
        <h1 className="page-title" style={{ marginTop: 16 }}>Sign in</h1>
        <div style={{ height: 16 }} />
        <label htmlFor="email">Email</label>
        <input id="email" type="email" autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} required />
        <div style={{ height: 12 }} />
        <label htmlFor="password">Password</label>
        <input id="password" type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required />
        <div style={{ height: 16 }} />
        {error ? <div className="err">{error}</div> : null}
        {error ? <div style={{ height: 12 }} /> : null}
        <button className="btn" disabled={busy} type="submit">
          {busy ? "Signing in…" : "Sign in"}
        </button>
      </form>
    </div>
  );
}
