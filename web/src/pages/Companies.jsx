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
  industry: "",
  contactPerson: "",
  contactEmail: "",
  website: "",
};

export default function Companies() {
  const { isAdmin } = useAuth();
  const [query, setQuery] = useState("");
  const [appliedQuery, setAppliedQuery] = useState("");
  const companies = useAsync(
    () =>
      isAdmin
        ? api("/companies", { query: { limit: 100, q: appliedQuery || undefined } })
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
        <CardHeader title="Companies are admin-only" />
        <p className="p-5 text-sm text-slate-500">
          Ask an administrator to manage the recruiting company catalogue.
        </p>
      </Card>
    );
  }

  async function create(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api("/companies", {
        method: "POST",
        body: {
          name: form.name,
          industry: form.industry || null,
          contactPerson: form.contactPerson || null,
          contactEmail: form.contactEmail || null,
          website: form.website || null,
        },
      });
      setForm(EMPTY);
      setShowCreate(false);
      companies.reload();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function toggle(company) {
    setError("");
    try {
      await api(`/companies/${company.id}`, {
        method: "PATCH",
        body: { active: !company.active },
      });
      companies.reload();
    } catch (err) {
      setError(err.message);
    }
  }

  const items = companies.data?.items || [];

  return (
    <div>
      <PageHeader title="Companies" subtitle="Recruiters available when creating drives">
        <button type="button" className="btn-primary" onClick={() => setShowCreate(!showCreate)}>
          <Icon name="plus" className="h-4 w-4" />
          {showCreate ? "Close" : "New company"}
        </button>
      </PageHeader>

      <ErrorBanner
        error={companies.error || (error ? { message: error } : null)}
        onRetry={() => companies.reload()}
      />

      {showCreate ? (
        <Card className="mb-5">
          <CardHeader title="Create company" subtitle="Renaming a company propagates to its drives" />
          <form onSubmit={create} className="grid gap-4 p-5 md:grid-cols-2">
            <Field label="Name">
              <input required className="input" value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} />
            </Field>
            <Field label="Industry">
              <input className="input" value={form.industry} onChange={(event) => setForm({ ...form, industry: event.target.value })} />
            </Field>
            <Field label="Contact person">
              <input className="input" value={form.contactPerson} onChange={(event) => setForm({ ...form, contactPerson: event.target.value })} />
            </Field>
            <Field label="Contact email">
              <input type="email" className="input" value={form.contactEmail} onChange={(event) => setForm({ ...form, contactEmail: event.target.value })} />
            </Field>
            <Field label="Website">
              <input className="input" placeholder="https://" value={form.website} onChange={(event) => setForm({ ...form, website: event.target.value })} />
            </Field>
            <div className="flex items-end">
              <button type="submit" className="btn-primary w-full" disabled={busy}>
                {busy ? "Creating…" : "Create company"}
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
              placeholder="Company or industry"
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
        {companies.loading ? (
          <Spinner />
        ) : items.length === 0 ? (
          <EmptyState title="No companies found" body="Add a company before publishing a drive." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[720px]">
              <thead className="bg-slate-50">
                <tr>
                  <th className="th">Company</th>
                  <th className="th">Industry</th>
                  <th className="th">Contact</th>
                  <th className="th">Drives</th>
                  <th className="th">Status</th>
                  <th className="th">Created</th>
                  <th className="th" />
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {items.map((company) => (
                  <tr key={company.id} className="hover:bg-slate-50">
                    <td className="td">
                      <p className="font-semibold text-slate-900">{company.name}</p>
                      {company.website ? (
                        <a className="link text-xs" href={company.website} target="_blank" rel="noreferrer">
                          {company.website}
                        </a>
                      ) : null}
                    </td>
                    <td className="td">{company.industry || "—"}</td>
                    <td className="td text-xs">
                      <p>{company.contactPerson || "—"}</p>
                      <p className="text-slate-500">{company.contactEmail || ""}</p>
                    </td>
                    <td className="td">{company.driveCount ?? 0}</td>
                    <td className="td">
                      <Badge tone={company.active ? "green" : "slate"}>
                        {company.active ? "Active" : "Inactive"}
                      </Badge>
                    </td>
                    <td className="td text-xs text-slate-500">{formatDate(company.createdAt)}</td>
                    <td className="td text-right">
                      <button type="button" className="link" onClick={() => toggle(company)}>
                        {company.active ? "Deactivate" : "Activate"}
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
