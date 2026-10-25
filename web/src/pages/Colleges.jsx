import { useState } from "react";
import { useAuth } from "../context/AuthContext";
import { api } from "../lib/api";
import { formatDate } from "../lib/format";
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
} from "../components/ui";

const EMPTY = {
  name: "",
  city: "",
  contactPerson: "",
  contactEmail: "",
  contactPhone: "",
};

export default function Colleges() {
  const { isAdmin } = useAuth();
  const [query, setQuery] = useState("");
  const [appliedQuery, setAppliedQuery] = useState("");
  const colleges = useAsync(
    () =>
      isAdmin
        ? api("/colleges", { query: { limit: 100, q: appliedQuery || undefined } })
        : Promise.resolve(null),
    [isAdmin, appliedQuery]
  );
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState(EMPTY);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  if (!isAdmin) {
    return (
      <Card>
        <CardHeader title="Colleges are admin-only" />
        <p className="p-5 text-sm text-slate-500">
          Ask an administrator to add or deactivate a college.
        </p>
      </Card>
    );
  }

  async function create(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api("/colleges", {
        method: "POST",
        body: {
          name: form.name,
          city: form.city || null,
          contactPerson: form.contactPerson || null,
          contactEmail: form.contactEmail || null,
          contactPhone: form.contactPhone || null,
        },
      });
      setForm(EMPTY);
      setShowCreate(false);
      colleges.reload();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function toggle(college) {
    setError("");
    try {
      await api(`/colleges/${college.id}`, {
        method: "PATCH",
        body: { active: !college.active },
      });
      colleges.reload();
    } catch (err) {
      setError(err.message);
    }
  }

  const items = colleges.data?.items || [];

  return (
    <div>
      <PageHeader title="Colleges" subtitle="Institutes in scope and their placement footprint">
        <button type="button" className="btn-primary" onClick={() => setShowCreate(!showCreate)}>
          <Icon name="plus" className="h-4 w-4" />
          {showCreate ? "Close" : "New college"}
        </button>
      </PageHeader>

      <ErrorBanner
        error={colleges.error || (error ? { message: error } : null)}
        onRetry={() => colleges.reload()}
      />

      {showCreate ? (
        <Card className="mb-5">
          <CardHeader title="Create college" subtitle="Only super admins can add colleges" />
          <form onSubmit={create} className="grid gap-4 p-5 md:grid-cols-2">
            <Field label="Name">
              <input required className="input" value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} />
            </Field>
            <Field label="City">
              <input className="input" value={form.city} onChange={(event) => setForm({ ...form, city: event.target.value })} />
            </Field>
            <Field label="Placement contact">
              <input className="input" value={form.contactPerson} onChange={(event) => setForm({ ...form, contactPerson: event.target.value })} />
            </Field>
            <Field label="Contact email">
              <input type="email" className="input" value={form.contactEmail} onChange={(event) => setForm({ ...form, contactEmail: event.target.value })} />
            </Field>
            <Field label="Contact phone">
              <input className="input" value={form.contactPhone} onChange={(event) => setForm({ ...form, contactPhone: event.target.value })} />
            </Field>
            <div className="flex items-end">
              <button type="submit" className="btn-primary w-full" disabled={busy}>
                {busy ? "Creating…" : "Create college"}
              </button>
            </div>
          </form>
        </Card>
      ) : null}

      <Card className="mb-5 p-4">
        <form
          className="flex flex-wrap items-end gap-3"
          onSubmit={(event) => {
            event.preventDefault();
            setAppliedQuery(query);
          }}
        >
          <label className="min-w-[240px] flex-1">
            <span className="label">Search</span>
            <input
              className="input"
              placeholder="College name or city"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
          </label>
          <button type="submit" className="btn-secondary">
            Apply
          </button>
        </form>
      </Card>

      <Card>
        {colleges.loading ? (
          <Spinner />
        ) : items.length === 0 ? (
          <EmptyState title="No colleges found" body="Create a college to start onboarding batches and students." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[720px]">
              <thead className="bg-slate-50">
                <tr>
                  <th className="th">College</th>
                  <th className="th">City</th>
                  <th className="th">Contact</th>
                  <th className="th">Students</th>
                  <th className="th">Batches</th>
                  <th className="th">Status</th>
                  <th className="th">Created</th>
                  <th className="th" />
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {items.map((college) => (
                  <tr key={college.id} className="hover:bg-slate-50">
                    <td className="td">
                      <p className="font-semibold text-slate-900">{college.name}</p>
                      <p className="text-xs text-slate-500">{college.id}</p>
                    </td>
                    <td className="td">{college.city || "—"}</td>
                    <td className="td text-xs">
                      <p>{college.contactPerson || "—"}</p>
                      <p className="text-slate-500">{college.contactEmail || ""}</p>
                    </td>
                    <td className="td">{college.studentCount ?? 0}</td>
                    <td className="td">{college.batchCount ?? 0}</td>
                    <td className="td">
                      <Badge tone={college.active ? "green" : "slate"}>
                        {college.active ? "Active" : "Inactive"}
                      </Badge>
                    </td>
                    <td className="td text-xs text-slate-500">{formatDate(college.createdAt)}</td>
                    <td className="td text-right">
                      <button type="button" className="link" onClick={() => toggle(college)}>
                        {college.active ? "Deactivate" : "Activate"}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
