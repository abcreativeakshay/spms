import { useState } from "react";
import { useAuth } from "../context/AuthContext";
import { api, download } from "../lib/api";
import { useAsync } from "../lib/useAsync";
import { Icon } from "../components/Icon";
import { Card, CardHeader, ErrorBanner, Field, PageHeader, Spinner } from "../components/ui";

const REPORTS = [
  { id: "placements", label: "Placements", description: "Student, company, CTC and placement status" },
  { id: "students", label: "Students", description: "Full profile, readiness and academic data" },
  { id: "applications", label: "Applications", description: "Drive pipeline and offer details" },
  { id: "attendance", label: "Attendance", description: "Present/absent counts and percentage" },
  { id: "drives", label: "Drives", description: "Drive catalogue with application counts" },
];

export default function Reports() {
  const { isAdmin } = useAuth();
  const colleges = useAsync(() => api("/colleges", { query: { limit: 100 } }), []);
  const batches = useAsync(() => api("/batches", { query: { limit: 100 } }), []);
  const [form, setForm] = useState({ report: "placements", format: "csv", collegeId: "", batchId: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [done, setDone] = useState("");

  if (!isAdmin) {
    return (
      <Card>
        <CardHeader title="Reports are admin-only" />
        <p className="p-5 text-sm text-slate-500">
          Ask an administrator for a CSV or PDF export. Student and trainer dashboards remain available.
        </p>
      </Card>
    );
  }

  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setDone("");
    try {
      await download("/reports/export", {
        report: form.report,
        format: form.format,
        collegeId: form.collegeId || undefined,
        batchId: form.batchId || undefined,
      });
      setDone(`${form.report} ${form.format.toUpperCase()} downloaded.`);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  const selected = REPORTS.find((report) => report.id === form.report);

  return (
    <div>
      <PageHeader title="Reports" subtitle="CSV and PDF exports scoped to your colleges" />
      <ErrorBanner error={colleges.error || batches.error || (error ? { message: error } : null)} />

      <div className="grid gap-5 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader title="Build an export" subtitle="Large exports are generated server-side" />
          <form onSubmit={submit} className="grid gap-4 p-5 md:grid-cols-2">
            <Field label="Report">
              <select className="input" value={form.report} onChange={(event) => setForm({ ...form, report: event.target.value })}>
                {REPORTS.map((report) => (
                  <option key={report.id} value={report.id}>
                    {report.label}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Format">
              <select className="input" value={form.format} onChange={(event) => setForm({ ...form, format: event.target.value })}>
                <option value="csv">CSV</option>
                <option value="pdf">PDF</option>
              </select>
            </Field>
            <Field label="College" hint="Blank exports every college you can see">
              <select className="input" value={form.collegeId} onChange={(event) => setForm({ ...form, collegeId: event.target.value })}>
                <option value="">All colleges in scope</option>
                {(colleges.data?.items || []).map((college) => (
                  <option key={college.id} value={college.id}>
                    {college.name}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Batch" hint="Optional; set after choosing a college if needed">
              <select className="input" value={form.batchId} onChange={(event) => setForm({ ...form, batchId: event.target.value })}>
                <option value="">All batches</option>
                {(batches.data?.items || []).map((batch) => (
                  <option key={batch.id} value={batch.id}>
                    {batch.name}
                  </option>
                ))}
              </select>
            </Field>
            <div className="md:col-span-2 flex flex-wrap items-center gap-3">
              <button type="submit" className="btn-primary" disabled={busy}>
                <Icon name="reports" className="h-4 w-4" />
                {busy ? "Generating…" : "Download export"}
              </button>
              {done ? <span className="text-sm font-semibold text-emerald-600">{done}</span> : null}
            </div>
          </form>
        </Card>

        <Card>
          <CardHeader title={selected?.label || "Report"} subtitle="What is included" />
          <div className="space-y-3 p-5 text-sm text-slate-600">
            <p>{selected?.description}</p>
            <ul className="space-y-2 text-xs text-slate-500">
              <li className="flex gap-2">
                <Icon name="check" className="h-4 w-4 text-emerald-500" />
                College scoping is enforced on the server.
              </li>
              <li className="flex gap-2">
                <Icon name="check" className="h-4 w-4 text-emerald-500" />
                PDF exports include a placement summary and up to 500 rows.
              </li>
              <li className="flex gap-2">
                <Icon name="check" className="h-4 w-4 text-emerald-500" />
                Exports are generated on demand; nothing is cached to disk.
              </li>
            </ul>
          </div>
        </Card>
      </div>
    </div>
  );
}
