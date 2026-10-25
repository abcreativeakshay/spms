import { useEffect, useState } from "react";
import { Link, Navigate, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { api } from "../lib/api";
import { Icon } from "./Icon";
import { Avatar, Badge, Spinner } from "./ui";

const NAV = {
  admin: [
    { to: "/", label: "Dashboard", icon: "dashboard", end: true },
    { to: "/students", label: "Students", icon: "students" },
    { to: "/batches", label: "Batches", icon: "batches" },
    { to: "/drives", label: "Drives", icon: "drives" },
    { to: "/applications", label: "Applications", icon: "applications" },
    { to: "/colleges", label: "Colleges", icon: "batches" },
    { to: "/companies", label: "Companies", icon: "drives" },
    { to: "/users", label: "People", icon: "students" },
    { to: "/reports", label: "Reports", icon: "reports" },
    { to: "/audit", label: "Audit log", icon: "shield" },
    { to: "/notifications", label: "Notifications", icon: "bell" },
  ],
  trainer: [
    { to: "/", label: "Dashboard", icon: "dashboard", end: true },
    { to: "/students", label: "Students", icon: "students" },
    { to: "/batches", label: "Batches", icon: "batches" },
    { to: "/drives", label: "Drives", icon: "drives" },
    { to: "/applications", label: "Applications", icon: "applications" },
    { to: "/notifications", label: "Notifications", icon: "bell" },
  ],
  student: [
    { to: "/", label: "Dashboard", icon: "dashboard", end: true },
    { to: "/profile", label: "My profile", icon: "user" },
    { to: "/drives", label: "Drives", icon: "drives" },
    { to: "/applications", label: "My applications", icon: "applications" },
    { to: "/notifications", label: "Notifications", icon: "bell" },
  ],
};

export default function Protected() {
  const { token, me, loading } = useAuth();
  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Spinner label="Signing you in…" />
      </div>
    );
  }
  if (!token || !me) return <Navigate to="/login" replace />;
  return <Outlet />;
}

export function AppLayout() {
  const { me, signOut } = useAuth();
  const location = useLocation();
  const [open, setOpen] = useState(false);
  const [unread, setUnread] = useState(0);

  useEffect(() => {
    setOpen(false);
  }, [location.pathname]);

  useEffect(() => {
    let cancelled = false;
    api("/notifications", { query: { unreadOnly: true, limit: 1 } })
      .then((page) => {
        if (!cancelled) setUnread(page?.items?.length ? 1 : 0);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [location.pathname]);

  const items = NAV[me?.role] || NAV.student;

  return (
    <div className="min-h-screen lg:flex">
      <aside
        className={`fixed inset-y-0 left-0 z-40 w-64 transform border-r border-slate-200 bg-white transition-transform lg:static lg:translate-x-0 ${
          open ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div className="flex h-16 items-center gap-2 border-b border-slate-100 px-5">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-600 text-sm font-extrabold text-white">
            SP
          </div>
          <div>
            <p className="text-sm font-bold leading-tight text-slate-900">SPMS</p>
            <p className="text-[11px] text-slate-500">Placement management</p>
          </div>
          <button
            type="button"
            className="ml-auto rounded-lg p-2 text-slate-500 hover:bg-slate-100 lg:hidden"
            onClick={() => setOpen(false)}
            aria-label="Close menu"
          >
            <Icon name="close" />
          </button>
        </div>

        <nav className="space-y-1 p-3">
          {items.map((item) => (
            <NavItem key={item.to} item={item} unread={item.icon === "bell" ? unread : 0} />
          ))}
        </nav>

        <div className="absolute inset-x-0 bottom-0 border-t border-slate-100 p-3">
          <div className="flex items-center gap-3 rounded-lg bg-slate-50 p-3">
            <Avatar name={me?.name} size="sm" />
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-semibold text-slate-900">{me?.name}</p>
              <p className="truncate text-xs text-slate-500">{me?.email}</p>
            </div>
          </div>
          <button
            type="button"
            onClick={signOut}
            className="mt-2 flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm font-semibold text-slate-600 hover:bg-slate-100"
          >
            <Icon name="logout" className="h-4 w-4" />
            Sign out
          </button>
        </div>
      </aside>

      {open ? (
        <button
          type="button"
          aria-label="Close menu overlay"
          className="fixed inset-0 z-30 bg-slate-900/30 lg:hidden"
          onClick={() => setOpen(false)}
        />
      ) : null}

      <div className="min-w-0 flex-1">
        <header className="sticky top-0 z-20 flex h-16 items-center gap-3 border-b border-slate-200 bg-white/90 px-4 backdrop-blur lg:px-8">
          <button
            type="button"
            className="rounded-lg p-2 text-slate-600 hover:bg-slate-100 lg:hidden"
            onClick={() => setOpen(true)}
            aria-label="Open menu"
          >
            <Icon name="menu" />
          </button>
          <div className="hidden items-center gap-2 text-xs text-slate-500 sm:flex">
            <span className="h-2 w-2 rounded-full bg-emerald-500" />
            Connected to SPMS API
          </div>
          <div className="ml-auto flex items-center gap-2">
            <Badge tone={me?.superAdmin ? "brand" : "slate"}>
              {me?.superAdmin ? "Super admin" : me?.role}
            </Badge>
            <Link
              to="/notifications"
              className="relative rounded-lg p-2 text-slate-600 hover:bg-slate-100"
              aria-label="Notifications"
            >
              <Icon name="bell" />
              {unread ? (
                <span className="absolute right-1.5 top-1.5 h-2 w-2 rounded-full bg-rose-500" />
              ) : null}
            </Link>
          </div>
        </header>
        <main className="mx-auto max-w-7xl px-4 py-6 lg:px-8 lg:py-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

function NavItem({ item, unread }) {
  const location = useLocation();
  const active = item.end
    ? location.pathname === item.to
    : location.pathname === item.to || location.pathname.startsWith(`${item.to}/`);
  return (
    <Link
      to={item.to}
      className={`flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-semibold transition ${
        active ? "bg-brand-50 text-brand-700" : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"
      }`}
    >
      <Icon name={item.icon} className="h-5 w-5" />
      <span className="flex-1">{item.label}</span>
      {unread ? <span className="h-2 w-2 rounded-full bg-rose-500" /> : null}
    </Link>
  );
}
