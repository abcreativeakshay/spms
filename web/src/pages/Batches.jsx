import { useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { api } from "../lib/api";
import { formatDate, pct } from "../lib/format";
import { useAsync } from "../lib/useAsync";
import { Icon } from "../components/Icon";
import {
  Badge,
  Card,
  CardHeader,
  EmptyState,
  ErrorBanner,
  Field,
  PageHeader,
  Spinner,
  StatusBadge,
} from "../components/ui";

export default function Batches() {
  const { isAdmin } = useAuth();
  const batches = useAsync(() => api("/batches", { query: { limit: 100 } }), []);
  const colleges = useAsync(() => api("/colleges", { query: { limit: 100 } }), []);
  const trainers = useAsync(
    () => (isAdmin ? api("/users", { query: { role: "trainer", limit: 100 } }) : Promise.resolve(null)),
    [isAdmin]
  );
  const [showCreate, setShowCreate] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState({
    name: "",
    course: "",
    collegeId: "",
    trainerIds: [],
    startDate: "",
    endDate: "",
    minAttendancePct: 75,
  });

  async function create(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api("/batches", {
        method: "POST",
        body: {
          ...form,
          minAttendancePct: Number(form.minAttendancePct),
          trainerIds: form.trainerIds,
        },
      });
      setShowCreate(false);
      setForm({
        name: "",
        course: "",
        collegeId: "",
        trainerIds: [],
        startDate: "",
        endDate: "",
        minAttendancePct: 75,
      });
      batches.reload();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <PageHeader title="Batches" subtitle="Cohorts, trainers and attendance thresholds">
        {isAdmin ? (
          <button type="button" className="btn-primary" onClick={() => setShowCreate(!showCreate)}>
            <Icon name="plus" className="h-4 w-4" />
            {showCreate ? "Close" : "New batch"}
          </button>
        ) : null}
      </PageHeader>

      <ErrorBanner error={batches.error || colleges.error || trainers.error || (error ? { message: error } : null)} />

      {showCreate ? (
        <Card className="mb-5">
          <CardHeader title="Create batch" subtitle="Trainers must belong to the selected college" />
          <form onSubmit={create} className="grid gap-4 p-5 md:grid-cols-2">
            <Field label="Batch name">
              <input required className="input" value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} />
            </Field>
            <Field label="Course">
              <input required className="input" value={form.course} onChange={(event) => setForm({ ...form, course: event.target.value })} />
            </Field>
            <Field label="College">
              <select required className="input" value={form.collegeId} onChange={(event) => setForm({ ...form, collegeId: event.target.value })}>
                <option value="">Select a college</option>
                {(colleges.data?.items || []).map((college) => (
                  <option key={college.id} value={college.id}>
                    {college.name}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Trainers" hint="Ctrl/Cmd click to select multiple">
              <select
                multiple
                className="input min-h-[92px]"
                value={form.trainerIds}
                onChange={(event) =>
                  setForm({
                    ...form,
                    trainerIds: Array.from(event.target.selectedOptions, (option) => option.value),
                  })
                }
              >
                {(trainers.data?.items || []).map((trainer) => (
                  <option key={trainer.id} value={trainer.id}>
                    {trainer.name}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Start date">
              <input required type="date" className="input" value={form.startDate} onChange={(event) => setForm({ ...form, startDate: event.target.value })} />
            </Field>
            <Field label="End date">
              <input required type="date" className="input" value={form.endDate} onChange={(event) => setForm({ ...form, endDate: event.target.value })} />
            </Field>
            <Field label="Minimum attendance %">
              <input type="number" min="0" max="100" className="input" value={form.minAttendancePct} onChange={(event) => setForm({ ...form, minAttendancePct: event.target.value })} />
            </Field>
            <div className="flex items-end">
              <button type="submit" className="btn-primary" disabled={busy}>
                {busy ? "Creating…" : "Create batch"}
              </button>
            </div>
          </form>
        </Card>
      ) : null}

      <Card>
        {batches.loading ? (
          <Spinner />
        ) : (batches.data?.items || []).length === 0 ? (
          <EmptyState title="No batches in scope" body="Create a batch to start enrolling students." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[840px]">
              <thead className="bg-slate-50">
                <tr>
                  <th className="th">Batch</th>
                  <th className="th">College</th>
                  <th className="th">Trainers</th>
                  <th className="th">Timeline</th>
                  <th className="th">Students</th>
                  <th className="th">Min attendance</th>
                  <th className="th">Status</th>
                  <th className="th" />
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {(batches.data?.items || []).map((batch) => (
                  <tr key={batch.id} className="hover:bg-slate-50">
                    <td className="td">
                      <p className="font-semibold text-slate-900">{batch.name}</p>
                      <p className="text-xs text-slate-500">{batch.course}</p>
                    </td>
                    <td className="td">{batch.collegeName}</td>
                    <td className="td text-xs">{(batch.trainerNames || []).join(", ") || "—"}</td>
                    <td className="td text-xs">
                      {formatDate(batch.startDate)} — {formatDate(batch.endDate)}
                    </td>
                    <td className="td">{batch.studentCount ?? 0}</td>
                    <td className="td">{pct(batch.minAttendancePct, 0)}</td>
                    <td className="td">
                      <StatusBadge status={batch.status} />
                    </td>
                    <td className="td text-right">
                      <Link to={`/batches/${batch.id}`} className="link">
                        Open
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <div className="mt-4 flex items-center gap-2 text-xs text-slate-500">
        <Badge tone="brand">{batches.data?.items?.length || 0}</Badge> batches in scope
      </div>
    </div>
  );
}
