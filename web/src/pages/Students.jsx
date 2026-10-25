import { useCallback, useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { api } from "../lib/api";
import { formatDate, pct, titleCase } from "../lib/format";
import { Avatar, Badge, Card, EmptyState, ErrorBanner, PageHeader, Spinner, StatusBadge } from "../components/ui";
import { Icon } from "../components/Icon";

const STATUS_OPTIONS = ["", "unplaced", "in_process", "placed", "opted_out"];

export default function Students() {
  const [searchParams] = useSearchParams();
  const { isAdmin } = useAuth();
  const [filters, setFilters] = useState({
    q: "",
    batchId: "",
    placementStatus: "",
    atRisk: searchParams.get("atRisk") === "true",
    minCgpa: "",
  });
  const [applied, setApplied] = useState(filters);
  const [items, setItems] = useState([]);
  const [nextCursor, setNextCursor] = useState(null);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState(null);
  const [batches, setBatches] = useState([]);
  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState(null);

  useEffect(() => {
    api("/batches", { query: { limit: 100 } })
      .then((page) => setBatches(page.items || []))
      .catch(() => {});
  }, []);

  const load = useCallback(
    async (currentFilters, cursor = null, append = false) => {
      if (append) setLoadingMore(true);
      else setLoading(true);
      setError(null);
      try {
        const query = {
          limit: 20,
          cursor: cursor || undefined,
          q: currentFilters.q || undefined,
          batchId: currentFilters.batchId || undefined,
          placementStatus: currentFilters.placementStatus || undefined,
          atRisk: currentFilters.atRisk ? true : undefined,
          minCgpa: currentFilters.minCgpa || undefined,
        };
        const page = await api("/students", { query });
        setItems((previous) => (append ? [...previous, ...(page.items || [])] : page.items || []));
        setNextCursor(page.nextCursor);
      } catch (err) {
        setError(err);
      } finally {
        setLoading(false);
        setLoadingMore(false);
      }
    },
    []
  );

  useEffect(() => {
    load(applied);
  }, [applied, load]);

  function submit(event) {
    event.preventDefault();
    setApplied({ ...filters });
  }

  function reset() {
    const cleared = { q: "", batchId: "", placementStatus: "", atRisk: false, minCgpa: "" };
    setFilters(cleared);
    setApplied(cleared);
  }

  async function importCsv(event) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    setImporting(true);
    setError(null);
    setImportResult(null);
    const form = new FormData();
    form.append("file", file);
    try {
      const result = await api("/students/import", { method: "POST", body: form });
      setImportResult(result);
      load(applied);
    } catch (err) {
      setError(err);
    } finally {
      setImporting(false);
    }
  }

  return (
    <div>
      <PageHeader title="Students" subtitle="Search profiles, readiness and placement status">
        <button type="button" onClick={reset} className="btn-secondary">
          Reset filters
        </button>
        {isAdmin ? (
          <label className="btn-primary cursor-pointer">
            {importing ? "Importing…" : "Import CSV"}
            <input type="file" className="hidden" accept=".csv,text/csv" onChange={importCsv} disabled={importing} />
          </label>
        ) : null}
      </PageHeader>

      {importResult ? (
        <div className="mb-5 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
          <p className="font-semibold">
            Import finished: {importResult.created} created, {importResult.failed} failed.
          </p>
          {importResult.errors?.length ? (
            <ul className="mt-1 list-inside list-disc text-xs">
              {importResult.errors.slice(0, 5).map((row, index) => (
                <li key={`${row.row}-${index}`}>
                  Row {row.row}: {row.message}
                </li>
              ))}
              {importResult.errors.length > 5 ? <li>…and {importResult.errors.length - 5} more.</li> : null}
            </ul>
          ) : null}
        </div>
      ) : null}

      <Card className="mb-5 p-4">
        <form onSubmit={submit} className="grid gap-3 md:grid-cols-12">
          <label className="relative md:col-span-4">
            <span className="label">Search</span>
            <Icon name="search" className="pointer-events-none absolute left-3 top-[34px] h-4 w-4 text-slate-400" />
            <input
              className="input pl-9"
              placeholder="Name, email or roll number"
              value={filters.q}
              onChange={(event) => setFilters({ ...filters, q: event.target.value })}
            />
          </label>
          <label className="md:col-span-3">
            <span className="label">Batch</span>
            <select
              className="input"
              value={filters.batchId}
              onChange={(event) => setFilters({ ...filters, batchId: event.target.value })}
            >
              <option value="">All batches</option>
              {batches.map((batch) => (
                <option key={batch.id} value={batch.id}>
                  {batch.name}
                </option>
              ))}
            </select>
          </label>
          <label className="md:col-span-2">
            <span className="label">Status</span>
            <select
              className="input"
              value={filters.placementStatus}
              onChange={(event) => setFilters({ ...filters, placementStatus: event.target.value })}
            >
              {STATUS_OPTIONS.map((status) => (
                <option key={status || "all"} value={status}>
                  {status ? titleCase(status) : "All statuses"}
                </option>
              ))}
            </select>
          </label>
          <label className="md:col-span-2">
            <span className="label">Min CGPA</span>
            <input
              type="number"
              step="0.1"
              min="0"
              max="10"
              className="input"
              placeholder="Any"
              value={filters.minCgpa}
              onChange={(event) => setFilters({ ...filters, minCgpa: event.target.value })}
            />
          </label>
          <div className="flex items-end gap-2 md:col-span-1">
            <button type="submit" className="btn-primary w-full">
              Apply
            </button>
          </div>
          <label className="flex items-center gap-2 text-sm text-slate-600 md:col-span-12">
            <input
              type="checkbox"
              className="h-4 w-4 rounded border-slate-300 text-brand-600"
              checked={filters.atRisk}
              onChange={(event) => setFilters({ ...filters, atRisk: event.target.checked })}
            />
            Only at-risk students
          </label>
        </form>
        {isAdmin ? (
          <p className="mt-3 text-xs text-slate-500">
            CSV import header: <code>name,email,collegeId,batchId,rollNo,degree,branch,gradYear,cgpa,skills</code>
            . Duplicate emails are reported per row.
          </p>
        ) : null}
      </Card>

      <ErrorBanner error={error} onRetry={() => load(applied)} />

      <Card>
        {loading ? (
          <Spinner />
        ) : items.length === 0 ? (
          <EmptyState title="No students match these filters" body="Try widening the search or resetting filters." />
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[760px]">
                <thead className="bg-slate-50">
                  <tr>
                    <th className="th">Student</th>
                    <th className="th">Batch</th>
                    <th className="th">CGPA</th>
                    <th className="th">Attendance</th>
                    <th className="th">Readiness</th>
                    <th className="th">Status</th>
                    <th className="th">Updated</th>
                    <th className="th" />
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {items.map((student) => (
                    <tr key={student.id} className="hover:bg-slate-50">
                      <td className="td">
                        <div className="flex items-center gap-3">
                          <Avatar name={student.name} size="sm" />
                          <div>
                            <p className="font-semibold text-slate-900">{student.name}</p>
                            <p className="text-xs text-slate-500">{student.rollNo || student.email}</p>
                          </div>
                        </div>
                      </td>
                      <td className="td">{student.batchName || "—"}</td>
                      <td className="td">{student.cgpa ?? "—"}</td>
                      <td className="td">
                        <div className="flex items-center gap-2">
                          <span>{pct(student.attendancePct)}</span>
                          {student.atRisk ? <Badge tone="rose">at risk</Badge> : null}
                        </div>
                      </td>
                      <td className="td">
                        <div className="flex items-center gap-2">
                          <div className="h-1.5 w-20 overflow-hidden rounded-full bg-slate-100">
                            <div
                              className="h-full rounded-full bg-brand-500"
                              style={{ width: `${Math.min(100, student.readinessScore || 0)}%` }}
                            />
                          </div>
                          <span className="text-xs font-semibold">{Math.round(student.readinessScore || 0)}</span>
                        </div>
                      </td>
                      <td className="td">
                        <StatusBadge status={student.placementStatus} />
                        {student.placedCompany ? (
                          <p className="mt-1 text-xs text-slate-500">{student.placedCompany}</p>
                        ) : null}
                      </td>
                      <td className="td text-xs text-slate-500">{formatDate(student.updatedAt)}</td>
                      <td className="td text-right">
                        <Link to={`/students/${student.id}`} className="link">
                          View
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {nextCursor ? (
              <div className="border-t border-slate-100 p-4 text-center">
                <button
                  type="button"
                  className="btn-secondary"
                  disabled={loadingMore}
                  onClick={() => load(applied, nextCursor, true)}
                >
                  {loadingMore ? "Loading…" : "Load more"}
                </button>
              </div>
            ) : null}
          </>
        )}
      </Card>
    </div>
  );
}
