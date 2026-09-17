"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { GsbLogo } from "@/components/Logo";
import { User, api, getSiteId, me, setSiteId } from "@/lib/api";

type NavItem = { href: string; label: string; owner?: boolean; icon: string };

const MAIN: NavItem[] = [
  { href: "/", label: "Home", icon: "home" },
  { href: "/attendance", label: "Attendance", icon: "people" },
  { href: "/plans", label: "Plan", icon: "plan" },
  { href: "/progress", label: "Progress", icon: "chart" },
  { href: "/today", label: "Today's Progress", icon: "today" },
  { href: "/issues", label: "Issues", icon: "alert" },
  { href: "/employees", label: "Employees", icon: "badge" },
  { href: "/master", label: "Master list", icon: "box" },
  { href: "/reports", label: "Reports", owner: true, icon: "doc" },
];

const MANAGE: NavItem[] = [
  { href: "/sites", label: "Projects", owner: true, icon: "pin" },
  { href: "/users", label: "Users", owner: true, icon: "users" },
];

export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [user, setUser] = useState<User | null>(null);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    me()
      .then((u) => {
        if (u.must_change_password) {
          window.location.href = "/change-password";
          return;
        }
        setUser(u);
        const current = getSiteId();
        if (!current && u.sites[0]) setSiteId(u.sites[0].id);
        if (current && !u.sites.some((s) => s.id === current) && u.sites[0]) {
          setSiteId(u.sites[0].id);
        }
      })
      .catch(() => {
        window.location.href = "/login";
      });
  }, []);

  useEffect(() => {
    setOpen(false);
  }, [pathname]);

  if (!user) {
    return (
      <div className="app-frame">
        <div className="empty">Loading GSB Infrastructure…</div>
      </div>
    );
  }

  const siteId = getSiteId();
  const site = user.sites.find((s) => s.id === siteId) || user.sites[0];
  const isOwner = user.global_role === "OWNER";
  const initials = user.name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0]?.toUpperCase())
    .join("");

  function active(href: string) {
    if (href === "/") return pathname === "/";
    if (href === "/attendance") return pathname.startsWith("/attendance");
    return pathname.startsWith(href);
  }

  async function logout() {
    try {
      await api("/api/v1/auth/logout", { method: "POST" });
    } catch {
      /* ignore */
    }
    window.location.href = "/login";
  }

  const visibleMain = MAIN.filter((item) => !item.owner || isOwner);
  const visibleManage = MANAGE.filter((item) => !item.owner || isOwner);

  const sidebar = (
    <>
      <p className="nav-kicker">Main</p>
      {visibleMain.map((item) => (
        <Link key={item.href} href={item.href} className={`side-link ${active(item.href) ? "active" : ""}`}>
          <NavIcon name={item.icon} />
          {item.label}
        </Link>
      ))}
      {visibleManage.length ? (
        <>
          <p className="nav-kicker">Manage</p>
          {visibleManage.map((item) => (
            <Link key={item.href} href={item.href} className={`side-link ${active(item.href) ? "active" : ""}`}>
              <NavIcon name={item.icon} />
              {item.label}
            </Link>
          ))}
        </>
      ) : null}
      <div className="side-foot">
        <div className="side-skyline" aria-hidden="true" />
        <strong>Building</strong>
        <span>cleaner tomorrow</span>
      </div>
    </>
  );

  return (
    <div className="app-frame">
      <header className="topbar">
        <button
          className="icon-btn ghost-on-teal menu-btn"
          type="button"
          aria-label="Main"
          title="Main"
          onClick={() => setOpen(true)}
        >
          <MenuIcon />
        </button>
        <Link href="/" className="topbar-brand" aria-label="GSB Infrastructure home">
          <GsbLogo height={36} />
        </Link>
        <div className="topbar-end">
          {site ? (
            user.sites.length > 1 ? (
              <select
                className="site-chip header-site"
                aria-label="Selected project"
                value={site.id}
                onChange={(e) => {
                  setSiteId(e.target.value);
                  window.location.reload();
                }}
              >
                {user.sites.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name} ({s.code})
                  </option>
                ))}
              </select>
            ) : (
              <div className="site-chip header-site">
                {site.name} ({site.code})
              </div>
            )
          ) : null}
          <div className="user-chip">
            <span className="avatar">{initials || "U"}</span>
            <span className="user-chip-text">
              <strong>{user.name}</strong>
              {isOwner ? "Owner" : "Authorized"}
            </span>
          </div>
          <button className="icon-btn ghost-on-teal" type="button" aria-label="Log out" title="Log out" onClick={logout}>
            <LogoutIcon />
          </button>
        </div>
      </header>

      <div className="workspace">
        <div className="main-col">{children}</div>
      </div>

      <nav className="bottom-nav" aria-label="Mobile">
        <Link href="/attendance" className={pathname.startsWith("/attendance") ? "active" : ""}>
          <NavIcon name="people" />
          Attendance
        </Link>
        <Link href="/plans" className={active("/plans") ? "active" : ""}>
          <NavIcon name="plan" />
          Plan
        </Link>
        <Link href="/progress" className={active("/progress") ? "active" : ""}>
          <NavIcon name="chart" />
          Progress
        </Link>
        <Link href="/today" className={active("/today") ? "active" : ""}>
          <NavIcon name="today" />
          Today&apos;s<br />Progress
        </Link>
        <Link href="/issues" className={active("/issues") ? "active" : ""}>
          <NavIcon name="alert" />
          Issues
        </Link>
      </nav>

      {open ? (
        <div className="drawer" onClick={() => setOpen(false)}>
          <div className="drawer-panel left" onClick={(e) => e.stopPropagation()}>
            <div className="drawer-head">
              <strong>Main</strong>
              <button className="icon-btn" type="button" aria-label="Close menu" onClick={() => setOpen(false)}>
                ×
              </button>
            </div>
            {site ? (
              user.sites.length > 1 ? (
                <select
                  className="site-chip full"
                  aria-label="Selected project"
                  value={site.id}
                  onChange={(e) => {
                    setSiteId(e.target.value);
                    window.location.reload();
                  }}
                >
                  {user.sites.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name} ({s.code})
                    </option>
                  ))}
                </select>
              ) : (
                <div className="site-chip full">
                  {site.name} ({site.code})
                </div>
              )
            ) : null}
            {sidebar}
            <button type="button" onClick={logout}>
              Log out
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function NavIcon({ name }: { name: string }) {
  const d: Record<string, string> = {
    home: "M4 10.5L12 4l8 6.5V20a1 1 0 01-1 1h-5v-6H10v6H5a1 1 0 01-1-1v-9.5z",
    people: "M8 11a3 3 0 100-6 3 3 0 000 6zm8 0a3 3 0 100-6 3 3 0 000 6zM4 19a4 4 0 014-4h2a4 4 0 014 4v1H4v-1zm10 1v-1a5.5 5.5 0 012-4.2 4 4 0 014 4.2V20h-6z",
    plan: "M8 3h8v2h3v16H5V5h3V3zm2 0v2h4V3h-4zM8 10h8v2H8v-2zm0 4h5v2H8v-2z",
    chart: "M5 19h14v2H5v-2zM7 10h3v7H7v-7zm7-5h3v12h-3V5zm-3.5 8h3v4h-3v-4z",
    badge: "M12 3l2.2 4.5 5 .7-3.6 3.5.9 4.9L12 14.8 7.5 18.6l.9-4.9L4.8 8.2l5-.7L12 3z",
    box: "M4 7l8-4 8 4v10l-8 4-8-4V7zm8 4l7-3.5M12 11v9M12 11L5 7.5",
    doc: "M7 3h8l4 4v14H7V3zm8 0v5h5",
    pin: "M12 21s7-5.4 7-11a7 7 0 10-14 0c0 5.6 7 11 7 11zm0-8a3 3 0 110-6 3 3 0 010 6z",
    users: "M9 11a3.5 3.5 0 100-7 3.5 3.5 0 000 7zm7.5 1a3 3 0 100-6 3 3 0 000 6zM3.5 20a5.5 5.5 0 0111 0v1h-11v-1zm12 .2A6.6 6.6 0 0014 20h7v-1a4.5 4.5 0 00-5.5-4.4",
    alert: "M12 3l10 18H2L12 3zm0 7v5m0 3h.01",
    today: "M8 3v3M16 3v3M4 9h16M6 5h12a2 2 0 012 2v12a2 2 0 01-2 2H6a2 2 0 01-2-2V7a2 2 0 012-2zm2 8h4v4H8v-4z",
  };
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d={d[name] || d.home} stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function MenuIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M4 7h16M4 12h16M4 17h16" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}

function LogoutIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M15 17l5-5-5-5M20 12H9" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M11 19H6a2 2 0 01-2-2V7a2 2 0 012-2h5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}
