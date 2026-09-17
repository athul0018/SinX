"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { User, api, getSiteId, me } from "@/lib/api";

type Dash = {
  date: string;
  site_name: string;
  site_code?: string;
  active_employees: number;
  morning_marked: number;
  evening_marked: number;
  present: number;
  absent: number;
  ot_hours: number;
  plans_open: number;
  plans_completed: number;
  issues_open?: number;
  issues_closed?: number;
  progress_not_started?: number;
  progress_going?: number;
  progress_hold?: number;
  progress_done?: number;
};

function greeting(now = new Date()) {
  const h = now.getHours();
  if (h < 12) return "Good morning";
  if (h < 17) return "Good afternoon";
  return "Good evening";
}

function prettyDate(iso: string) {
  const d = new Date(`${iso}T12:00:00`);
  return {
    weekday: d.toLocaleDateString(undefined, { weekday: "long" }),
    rest: d.toLocaleDateString(undefined, { day: "numeric", month: "long", year: "numeric" }),
  };
}

export default function HomePage() {
  const [dash, setDash] = useState<Dash | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    const siteId = getSiteId();
    if (!siteId) return;
    Promise.all([me(), api<Dash>(`/api/v1/sites/${siteId}/dashboard`)])
      .then(([u, data]) => {
        setUser(u);
        setDash(data);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load"));
  }, []);

  const firstName = user?.name.split(/\s+/)[0] || "";
  const planTotal = dash ? dash.plans_open + dash.plans_completed : 0;
  const presentPct = dash && dash.active_employees ? Math.round((dash.present / dash.active_employees) * 100) : 0;
  const planPct = planTotal ? Math.round((dash!.plans_completed / planTotal) * 100) : 0;
  const dateBits = dash ? prettyDate(dash.date) : null;

  const donut = useMemo(() => {
    if (!dash || !dash.active_employees) return "conic-gradient(#d0d5dd 0 100%)";
    const p = (dash.present / dash.active_employees) * 100;
    return `conic-gradient(#014465 0 ${p}%, #d0d5dd ${p}% 100%)`;
  }, [dash]);

  const issueDonut = useMemo(() => {
    if (!dash) return "conic-gradient(#d0d5dd 0 100%)";
    const open = dash.issues_open || 0;
    const closed = dash.issues_closed || 0;
    const total = open + closed;
    if (!total) return "conic-gradient(#d0d5dd 0 100%)";
    const o = (open / total) * 100;
    return `conic-gradient(#b42318 0 ${o}%, #067647 ${o}% 100%)`;
  }, [dash]);

  const progressDonut = useMemo(() => {
    if (!dash) return "conic-gradient(#d0d5dd 0 100%)";
    const idle = dash.progress_not_started || 0;
    const going = dash.progress_going || 0;
    const hold = dash.progress_hold || 0;
    const done = dash.progress_done || 0;
    const total = idle + going + hold + done;
    if (!total) return "conic-gradient(#d0d5dd 0 100%)";
    const i = (idle / total) * 100;
    const g = (going / total) * 100;
    const h = (hold / total) * 100;
    return `conic-gradient(#667085 0 ${i}%, #eaaa08 ${i}% ${i + g}%, #b42318 ${i + g}% ${i + g + h}%, #067647 ${i + g + h}% 100%)`;
  }, [dash]);

  return (
    <div className="page dash">
      <div className="dash-hero">
        <div>
          <h1 className="page-title">
            {greeting()}{firstName ? `, ${firstName}` : ""}
          </h1>
          <p className="page-sub">Here&apos;s today&apos;s overview for your project.</p>
        </div>
        <div className="dash-meta">
          {dash ? (
            <div className="meta-card">
              <span className="meta-kicker">Project name</span>
              <strong>
                {dash.site_name}
                {dash.site_code ? ` (${dash.site_code})` : ""}
              </strong>
            </div>
          ) : null}
          {dateBits ? (
            <div className="meta-card">
              <span className="meta-kicker">{dateBits.weekday}</span>
              <strong>{dateBits.rest}</strong>
            </div>
          ) : null}
        </div>
      </div>

      {error ? <div className="err">{error}</div> : null}
      {!dash && !error ? <div className="empty">Loading dashboard…</div> : null}

      {dash ? (
        <>
          <div className="kpi-row">
            <Kpi
              tone="ok"
              label="Today's attendance"
              value={`${dash.present} / ${dash.active_employees}`}
              pct={presentPct}
              href="/attendance"
            />
            <Kpi tone="warn" label="OT hours today" value={String(dash.ot_hours)} pct={dash.ot_hours ? 100 : 0} href="/attendance" />
            <Kpi
              tone="bad"
              label="Open plans"
              value={`${dash.plans_open} / ${planTotal || dash.plans_open}`}
              pct={planTotal ? 100 - planPct : 0}
              href="/plans"
            />
            <Kpi
              tone="info"
              label="Open issues"
              value={String(dash.issues_open || 0)}
              pct={dash.issues_open ? 100 : 0}
              href="/issues"
            />
          </div>

          <div className="dash-charts">
              <section className="card">
                <div className="card-head">
                  <h2>Today&apos;s attendance</h2>
                  <Link href="/attendance">View Details →</Link>
                </div>
                <div className="manpower">
                  <div className="donut" style={{ background: donut }}>
                    <div className="donut-hole">
                      <b>{`${dash.present} / ${dash.active_employees}`}</b>
                      <span>Today&apos;s attendance</span>
                    </div>
                  </div>
                  <ul className="legend">
                    <li>
                      <i className="dot present" /> Present <b>{dash.present}</b>
                    </li>
                    <li>
                      <i className="dot unmarked" /> Not marked / absent <b>{Math.max(0, dash.active_employees - dash.present)}</b>
                    </li>
                  </ul>
                </div>
              </section>

              <section className="card">
                <div className="card-head">
                  <h2>Issues</h2>
                  <Link href="/issues">View Details →</Link>
                </div>
                <div className="manpower">
                  <div className="donut" style={{ background: issueDonut }}>
                    <div className="donut-hole">
                      <b>{(dash.issues_open || 0) + (dash.issues_closed || 0)}</b>
                      <span>Total</span>
                    </div>
                  </div>
                  <ul className="legend">
                    <li>
                      <i className="dot issue-open" /> Raised <b>{dash.issues_open || 0}</b>
                    </li>
                    <li>
                      <i className="dot issue-closed" /> Closed <b>{dash.issues_closed || 0}</b>
                    </li>
                  </ul>
                </div>
              </section>

              <section className="card">
                <div className="card-head">
                  <h2>Progress</h2>
                  <Link href="/progress">View Details →</Link>
                </div>
                <div className="manpower">
                  <div className="donut" style={{ background: progressDonut }}>
                    <div className="donut-hole">
                      <b>
                        {(dash.progress_not_started || 0) +
                          (dash.progress_going || 0) +
                          (dash.progress_hold || 0) +
                          (dash.progress_done || 0)}
                      </b>
                      <span>Total</span>
                    </div>
                  </div>
                  <ul className="legend">
                    <li>
                      <i className="dot unmarked" /> Not started <b>{dash.progress_not_started || 0}</b>
                    </li>
                    <li>
                      <i className="dot progress-going" /> Progress <b>{dash.progress_going || 0}</b>
                    </li>
                    <li>
                      <i className="dot issue-open" /> Hold <b>{dash.progress_hold || 0}</b>
                    </li>
                    <li>
                      <i className="dot issue-closed" /> Completed <b>{dash.progress_done || 0}</b>
                    </li>
                  </ul>
                </div>
              </section>
          </div>

          <div className="dash-grid lower">
            <section className="card">
              <div className="card-head">
                <h2>Pending Actions</h2>
              </div>
              <div className="pending">
                {dash.plans_open ? (
                  <Link href="/progress">
                    <span>
                      <strong>
                        {dash.plans_open} plan{dash.plans_open === 1 ? "" : "s"} pending
                      </strong>
                      Record progress
                    </span>
                    <em>→</em>
                  </Link>
                ) : null}
                {dash.issues_open ? (
                  <Link href="/issues">
                    <span>
                      <strong>
                        {dash.issues_open} open issue{dash.issues_open === 1 ? "" : "s"}
                      </strong>
                      Review and close
                    </span>
                    <em>→</em>
                  </Link>
                ) : null}
                {!dash.plans_open && !dash.issues_open ? (
                  <p className="muted">All documents and project actions are up to date.</p>
                ) : null}
              </div>
            </section>
            <aside className="promo">
              <h2>Reliable Infrastructure for a Cleaner Tomorrow</h2>
              <img src="/brand/gsb-logo.png?v=2" alt="" />
            </aside>
          </div>
        </>
      ) : null}
    </div>
  );
}

function Kpi({
  tone,
  label,
  value,
  pct,
  href,
}: {
  tone: string;
  label: string;
  value: string;
  pct: number;
  href: string;
}) {
  return (
    <Link href={href} className={`kpi ${tone}`}>
      <b>{value}</b>
      <span>{label}</span>
      <i>
        <u style={{ width: `${Math.min(100, Math.max(0, pct))}%` }} />
      </i>
    </Link>
  );
}
