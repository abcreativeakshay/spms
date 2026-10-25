import { useState } from "react";
import { useAuth } from "../context/AuthContext";
import { api } from "../lib/api";
import { csvList, formatDate, number, titleCase } from "../lib/format";
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

function future(days) {
  return new Date(Date.now() + days * 86400000).toISOString().slice(0, 10);
}

export default function Drives() {
  const { isAdmin, isStaff } = useAuth();
  const [status, setStatus] = useState("");
  const drives = useAsync(
    () => api("/drives", { query: { limit: 100, status: status || undefined } }),
    [status]
  );
  const companies = useAsync(
    () => (isAdmin ? api("/companies", { query: { limit: 100 } }) : Promise.resolve(null)),
    [isAdmin]
  );
  const colleges = useAsync(() => api("/colleges", { query: { limit: 100 } }), []);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({
    companyId: "",
    role: "",
    ctc: 8,
    location: "",
    driveDate: future(21),
    deadline: future(14),
    rounds: "Aptitude, Technical, HR",
    minCgpa: 6,
    minAttendance: 70,
    minAssessmentAvg: 0,
    branches: "",
    jobDescription: "",
    allowDreamOffer: false,
    status: "open",
  });
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState("");

  async function create(event) {
    event.preventDefault();
    setBusy(true);
    setActionError("");
    try {
      await api("/drives", {
        method: "POST",
        body: {
          companyId: form.companyId,
          role: form.role,
          ctc: Number(form.ctc),
          location: form.location || null,
          driveDate: form.driveDate,
          deadline: form.deadline,
          rounds: csvList(form.rounds).map((name) => ({ name })),
          eligibility: {
            minCgpa: Number(form.minCgpa),
            minAttendance: Number(form.minAttendance),
            minAssessmentAvg: Number(form.minAssessmentAvg),
            batchIds: [],
            collegeIds: [],
            branches: csvList(form.branches),
          },
          collegeIds: [],
          status: form.status,
          allowDreamOffer: form.allowDreamOffer,
          jobDescription: form.jobDescription || null,
        },
      });
      setShowCreate(false);
      drives.reload();
    } catch (err) {
      setActionError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function apply(driveId) {
    setActionError("");
    try {
      await api(`/drives/${driveId}/apply`, { method: "POST", body: { coverNote: null } });
      drives.reload();
    } catch (err) {
      setActionError(err.message);
    }
  }

  async function changeStatus(driveId, next) {
    setActionError("");
    try {
      await api(`/drives/${driveId}`, { method: "PATCH", body: { status: next } });
      drives.reload();
    } catch (err) {
      setActionError(err.message);
    }
  }

  return (
    <div>
      <PageHeader title="Placement drives" subtitle="Eligibility, applications and offers">
        <select className="input w-40" value={status} onChange={(event) => setStatus(event.target.value)} aria-label="Filter status">
          <option value="">All statuses</option>
          {["draft", "open", "closed", "completed", "cancelled"].map((value) => (
            <option key={value} value={value}>
              {titleCase(value)}
            </option>
          ))}
        </select>
        {isAdmin ? (
          <button type="button" className="btn-primary" onClick={() => setShowCreate(!showCreate)}>
            <Icon name="plus" className="h-4 w-4" />
            {showCreate ? "Close" : "New drive"}
          </button>
        ) : null}
      </PageHeader>

      <ErrorBanner
        error={
          drives.error ||
          companies.error ||
          colleges.error ||
          (actionError ? { message: actionError } : null)
        }
      />

      {showCreate ? (
        <Card className="mb-5">
          <CardHeader title="Create drive" subtitle="Eligibility is evaluated live for every student" />
          <form onSubmit={create} className="grid gap-4 p-5 md:grid-cols-3">
            <Field label="Company">
              <select required className="input" value={form.companyId} onChange={(event) => setForm({ ...form, companyId: event.target.value })}>
                <option value="">Select a company</option>
                {(companies.data?.items || []).map((company) => (
                  <option key={company.id} value={company.id}>
                    {company.name}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Role">
              <input required className="input" value={form.role} onChange={(event) => setForm({ ...form, role: event.target.value })} />
            </Field>
            <Field label="CTC (LPA)">
              <input required type="number" min="0" step="0.1" className="input" value={form.ctc} onChange={(event) => setForm({ ...form, ctc: event.target.value })} />
            </Field>
            <Field label="Location">
              <input className="input" value={form.location} onChange={(event) => setForm({ ...form, location: event.target.value })} />
            </Field>
            <Field label="Drive date">
              <input required type="date" className="input" value={form.driveDate} onChange={(event) => setForm({ ...form, driveDate: event.target.value })} />
            </Field>
            <Field label="Application deadline">
              <input required type="date" className="input" value={form.deadline} onChange={(event) => setForm({ ...form, deadline: event.target.value })} />
            </Field>
            <Field label="Rounds" hint="Comma separated">
              <input className="input" value={form.rounds} onChange={(event) => setForm({ ...form, rounds: event.target.value })} />
            </Field>
            <Field label="Minimum CGPA">
              <input type="number" min="0" max="10" step="0.1" className="input" value={form.minCgpa} onChange={(event) => setForm({ ...form, minCgpa: event.target.value })} />
            </Field>
            <Field label="Minimum attendance %">
              <input type="number" min="0" max="100" className="input" value={form.minAttendance} onChange={(event) => setForm({ ...form, minAttendance: event.target.value })} />
            </Field>
            <Field label="Eligible branches" hint="Comma separated; blank means all">
              <input className="input" value={form.branches} onChange={(event) => setForm({ ...form, branches: event.target.value })} />
            </Field>
            <Field label="Status">
              <select className="input" value={form.status} onChange={(event) => setForm({ ...form, status: event.target.value })}>
                {["draft", "open"].map((value) => (
                  <option key={value} value={value}>
                    {titleCase(value)}
                  </option>
                ))}
              </select>
            </Field>
            <div className="flex items-end">
              <label className="flex items-center gap-2 pb-2 text-sm text-slate-600">
                <input
                  type="checkbox"
                  className="h-4 w-4 rounded border-slate-300 text-brand-600"
                  checked={form.allowDreamOffer}
                  onChange={(event) => setForm({ ...form, allowDreamOffer: event.target.checked })}
                />
                Allow dream offers
              </label>
            </div>
            <div className="md:col-span-3">
              <Field label="Job description">
                <textarea className="input" rows={2} value={form.jobDescription} onChange={(event) => setForm({ ...form, jobDescription: event.target.value })} />
              </Field>
            </div>
            <div className="md:col-span-3">
              <button type="submit" className="btn-primary" disabled={busy}>
                {busy ? "Creating…" : "Create drive"}
              </button>
            </div>
          </form>
        </Card>
      ) : null}

      {drives.loading ? (
        <Spinner />
      ) : (drives.data?.items || []).length === 0 ? (
        <Card>
          <EmptyState title="No drives in scope" body={isStaff ? "Create a drive to open applications." : "New drives will appear here."} />
        </Card>
      ) : (
        <div className="grid gap-4 xl:grid-cols-2">
          {(drives.data?.items || []).map((drive) => {
            const eligibility = drive.eligibilityResult;
            const application = drive.application;
            return (
              <Card key={drive.id} className="flex flex-col">
                <div className="flex items-start justify-between gap-3 border-b border-slate-100 p-5">
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <h2 className="text-base font-bold text-slate-900">{drive.companyName}</h2>
                      <StatusBadge status={drive.status} />
                      {drive.allowDreamOffer ? <Badge tone="amber">Dream offer</Badge> : null}
                    </div>
                    <p className="mt-0.5 text-sm text-slate-600">
                      {drive.role} · {number(drive.ctc, 1)} LPA · {drive.location || "Location TBD"}
                    </p>
                  </div>
                  {eligibility ? (
                    <Badge tone={eligibility.eligible ? "green" : "rose"}>
                      {eligibility.eligible ? "You are eligible" : "Not eligible"}
                    </Badge>
                  ) : null}
                </div>

                <div className="grid grid-cols-2 gap-3 p-5 text-sm sm:grid-cols-4">
                  <Info label="Drive" value={formatDate(drive.driveDate)} />
                  <Info label="Deadline" value={formatDate(drive.deadline)} />
                  <Info label="Rounds" value={drive.rounds?.length || 0} />
                  <Info label="Applied" value={drive.stats?.applied ?? 0} />
                </div>

                {drive.jobDescription ? (
                  <p className="px-5 pb-3 text-sm text-slate-600">{drive.jobDescription}</p>
                ) : null}

                {drive.rounds?.length ? (
                  <div className="flex flex-wrap gap-1.5 px-5 pb-4">
                    {drive.rounds.map((round, index) => (
                      <Badge key={`${round.name}-${index}`} tone="slate">
                        {index + 1}. {round.name}
                      </Badge>
                    ))}
                  </div>
                ) : null}

                <div className="mt-auto flex flex-wrap items-center gap-2 border-t border-slate-100 px-5 py-3">
                  <Badge tone="blue">
                    Min CGPA {drive.eligibility?.minCgpa ?? 0}
                  </Badge>
                  <Badge tone="blue">
                    Min attendance {drive.eligibility?.minAttendance ?? 0}%
                  </Badge>
                  {application ? (
                    <div className="ml-auto flex items-center gap-2">
                      <span className="text-xs text-slate-500">Your application:</span>
                      <StatusBadge status={application.status} />
                    </div>
                  ) : eligibility?.eligible ? (
                    <button type="button" className="btn-primary ml-auto" onClick={() => apply(drive.id)}>
                      Apply now
                    </button>
                  ) : null}
                  {isAdmin ? (
                    <select
                      className="ml-auto rounded-lg border border-slate-300 px-2 py-1 text-xs"
                      value={drive.status}
                      onChange={(event) => changeStatus(drive.id, event.target.value)}
                      aria-label="Change status"
                    >
                      {["draft", "open", "closed", "completed", "cancelled"].map((value) => (
                        <option key={value} value={value}>
                          {titleCase(value)}
                        </option>
                      ))}
                    </select>
                  ) : null}
                </div>

                {eligibility && !eligibility.eligible && eligibility.reasons?.length ? (
                  <div className="border-t border-rose-100 bg-rose-50 px-5 py-3">
                    <p className="text-xs font-semibold uppercase tracking-wide text-rose-600">
                      Why you are not eligible
                    </p>
                    <ul className="mt-1 list-inside list-disc text-xs text-rose-700">
                      {eligibility.reasons.map((reason) => (
                        <li key={reason}>{reason}</li>
                      ))}
                    </ul>
                  </div>
                ) : null}
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}

function Info({ label, value }) {
  return (
    <div>
      <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">{label}</p>
      <p className="mt-0.5 text-sm font-medium text-slate-800">{value}</p>
    </div>
  );
}
