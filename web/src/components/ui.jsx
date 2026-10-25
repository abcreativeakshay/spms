import { Link } from "react-router-dom";
import { titleCase } from "../lib/format";
import { Icon } from "./Icon";

const TONES = {
  slate: "bg-slate-100 text-slate-700",
  brand: "bg-brand-50 text-brand-700",
  green: "bg-emerald-50 text-emerald-700",
  amber: "bg-amber-50 text-amber-700",
  rose: "bg-rose-50 text-rose-700",
  blue: "bg-sky-50 text-sky-700",
};

export function Badge({ children, tone = "slate", className = "" }) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-semibold ${TONES[tone] || TONES.slate} ${className}`}
    >
      {children}
    </span>
  );
}

export function statusTone(status) {
  switch (status) {
    case "placed":
    case "selected":
    case "cleared":
    case "open":
    case "active":
      return "green";
    case "in_process":
    case "shortlisted":
    case "applied":
      return "blue";
    case "rejected":
    case "absent":
      return "rose";
    case "withdrawn":
    case "cancelled":
    case "archived":
      return "slate";
    case "draft":
    case "planned":
      return "amber";
    default:
      return "slate";
  }
}

export function StatusBadge({ status }) {
  return <Badge tone={statusTone(status)}>{titleCase(status || "—")}</Badge>;
}

export function Card({ children, className = "" }) {
  return <div className={`card ${className}`}>{children}</div>;
}

export function CardHeader({ title, subtitle, action }) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-3 border-b border-slate-100 px-5 py-4">
      <div>
        <h2 className="text-sm font-semibold text-slate-900">{title}</h2>
        {subtitle ? <p className="mt-0.5 text-xs text-slate-500">{subtitle}</p> : null}
      </div>
      {action}
    </div>
  );
}

export function PageHeader({ title, subtitle, children }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">{title}</h1>
        {subtitle ? <p className="mt-1 text-sm text-slate-500">{subtitle}</p> : null}
      </div>
      {children ? <div className="flex flex-wrap items-center gap-2">{children}</div> : null}
    </div>
  );
}

export function StatCard({ label, value, hint, icon = "dashboard", tone = "brand" }) {
  return (
    <Card className="p-5">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</p>
          <p className="mt-2 text-2xl font-bold text-slate-900">{value}</p>
          {hint ? <p className="mt-1 text-xs text-slate-500">{hint}</p> : null}
        </div>
        <span className={`rounded-lg p-2 ${TONES[tone] || TONES.brand}`}>
          <Icon name={icon} className="h-5 w-5" />
        </span>
      </div>
    </Card>
  );
}

export function Progress({ value = 0, tone = "brand", className = "" }) {
  const tones = {
    brand: "bg-brand-600",
    green: "bg-emerald-500",
    amber: "bg-amber-500",
    rose: "bg-rose-500",
  };
  return (
    <div className={`h-2 w-full overflow-hidden rounded-full bg-slate-100 ${className}`}>
      <div
        className={`h-full rounded-full transition-all ${tones[tone] || tones.brand}`}
        style={{ width: `${Math.max(0, Math.min(100, Number(value) || 0))}%` }}
      />
    </div>
  );
}

export function ReadinessRing({ value = 0, size = 132 }) {
  const radius = size / 2 - 10;
  const circumference = 2 * Math.PI * radius;
  const clamped = Math.max(0, Math.min(100, Number(value) || 0));
  const offset = circumference - (clamped / 100) * circumference;
  return (
    <div className="relative" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke="#e2e8f0" strokeWidth="10" />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="#4f46e5"
          strokeWidth="10"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-2xl font-bold text-slate-900">{Math.round(clamped)}</span>
        <span className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">
          readiness
        </span>
      </div>
    </div>
  );
}

function compactLabel(value) {
  const text = String(value ?? "");
  return /^\d{4}-\d{2}-\d{2}/.test(text) ? text.slice(5) : text;
}

export function MiniBars({ data = [], valueKey = "value", labelKey = "label", className = "" }) {
  const max = Math.max(...data.map((item) => Number(item[valueKey]) || 0), 1);
  return (
    <div className={`flex items-end gap-1.5 ${className}`} style={{ height: 96 }} role="img">
      {data.length === 0 ? (
        <p className="text-xs text-slate-400">No data yet</p>
      ) : (
        data.map((item, index) => (
          <div key={`${item[labelKey]}-${index}`} className="group relative flex flex-1 flex-col items-center justify-end gap-1">
            <span className="pointer-events-none absolute -top-6 hidden rounded bg-slate-900 px-1.5 py-0.5 text-[10px] text-white group-hover:block">
              {Math.round(Number(item[valueKey]) || 0)}
            </span>
            <div
              className="w-full rounded-t bg-brand-500/80 transition group-hover:bg-brand-600"
              style={{ height: `${Math.max(4, ((Number(item[valueKey]) || 0) / max) * 80)}px` }}
            />
            <span className="max-w-full truncate text-[9px] text-slate-400">
              {compactLabel(item[labelKey])}
            </span>
          </div>
        ))
      )}
    </div>
  );
}

export function Spinner({ label = "Loading…" }) {
  return (
    <div className="flex items-center justify-center gap-3 py-12 text-sm text-slate-500">
      <span className="h-5 w-5 animate-spin rounded-full border-2 border-slate-200 border-t-brand-600" />
      {label}
    </div>
  );
}

export function EmptyState({ title = "Nothing here yet", body, action }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 px-6 py-14 text-center">
      <div className="rounded-full bg-slate-100 p-3 text-slate-400">
        <Icon name="search" />
      </div>
      <h3 className="text-sm font-semibold text-slate-900">{title}</h3>
      {body ? <p className="max-w-md text-sm text-slate-500">{body}</p> : null}
      {action}
    </div>
  );
}

export function ErrorBanner({ error, onRetry }) {
  if (!error) return null;
  return (
    <div className="mb-5 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
      <span>{error.message || String(error)}</span>
      {onRetry ? (
        <button type="button" onClick={onRetry} className="font-semibold text-rose-700 underline">
          Retry
        </button>
      ) : null}
    </div>
  );
}

export function Field({ label, children, hint }) {
  return (
    <label className="block">
      <span className="label">{label}</span>
      {children}
      {hint ? <span className="mt-1 block text-xs text-slate-400">{hint}</span> : null}
    </label>
  );
}

export function Avatar({ name = "", size = "md" }) {
  const sizes = { sm: "h-8 w-8 text-xs", md: "h-10 w-10 text-sm", lg: "h-14 w-14 text-lg" };
  const letters = name
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join("");
  return (
    <span
      className={`inline-flex shrink-0 items-center justify-center rounded-full bg-brand-100 font-bold text-brand-700 ${sizes[size] || sizes.md}`}
    >
      {letters || "?"}
    </span>
  );
}

export function Tabs({ tabs, active, onChange }) {
  return (
    <div className="flex flex-wrap gap-1 rounded-lg bg-slate-100 p-1" role="tablist">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          type="button"
          role="tab"
          aria-selected={active === tab.id}
          onClick={() => onChange(tab.id)}
          className={`rounded-md px-3 py-1.5 text-sm font-semibold transition ${
            active === tab.id ? "bg-white text-brand-700 shadow-sm" : "text-slate-600 hover:text-slate-900"
          }`}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}

export function BackLink({ to, children = "Back" }) {
  return (
    <Link to={to} className="inline-flex items-center gap-1 text-sm font-semibold text-slate-500 hover:text-slate-800">
      <Icon name="arrow" className="h-4 w-4 rotate-180" />
      {children}
    </Link>
  );
}
