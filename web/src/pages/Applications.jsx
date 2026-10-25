import { useState } from "react";
import { useAuth } from "../context/AuthContext";
import { api } from "../lib/api";
import { formatDate, formatDateTime, titleCase } from "../lib/format";
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

export default function Applications() {
  const { isAdmin, isStudent } = useAuth();
  const [statusFilter, setStatusFilter] = useState("");
  const applications = useAsync(
    () => api("/applications", { query: { limit: 100, status: statusFilter || undefined } }),
    [statusFilter]
  );
  const [selected, setSelected] = useState(null);
  const [error, setError] = useState("");

  function updateSelected(updated) {
    setSelected(updated);
    applications.reload();
  }

  return (
    <div>
      <PageHeader
        title={isStudent ? "My applications" : "Applications"}
        subtitle={isStudent ? "Track every drive you have applied to" : "Advance rounds and record outcomes"}
      >
        <select
          className="input w-44"
          value={statusFilter}
          onChange={(event) => setStatusFilter(event.target.value)}
          aria-label="Filter by status"
        >
          <option value="">All statuses</option>
          {["applied", "shortlisted", "in_process", "selected", "rejected", "withdrawn"].map((status) => (
            <option key={status} value={status}>
              {titleCase(status)}
            </option>
          ))}
        </select>
      </PageHeader>

      <ErrorBanner
        error={applications.error || (error ? { message: error } : null)}
        onRetry={() => applications.reload()}
      />

      <Card>
        {applications.loading ? (
          <Spinner />
        ) : (applications.data?.items || []).length === 0 ? (
          <EmptyState
            title="No applications yet"
            body={isStudent ? "Apply to an open drive to see it here." : "Applications appear as students apply to drives."}
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[820px]">
              <thead className="bg-slate-50">
                <tr>
                  <th className="th">Student</th>
                  <th className="th">Company</th>
                  <th className="th">Role</th>
                  <th className="th">Status</th>
                  <th className="th">Current round</th>
                  <th className="th">Applied</th>
                  <th className="th">Offer</th>
                  <th className="th" />
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {(applications.data?.items || []).map((application) => (
                  <tr key={application.id} className="hover:bg-slate-50">
                    <td className="td">
                      <p className="font-semibold text-slate-900">{application.studentName}</p>
                      <p className="text-xs text-slate-500">{application.batchName || application.studentEmail}</p>
                    </td>
                    <td className="td">{application.companyName}</td>
                    <td className="td">{application.driveRole}</td>
                    <td className="td">
                      <StatusBadge status={application.status} />
                    </td>
                    <td className="td">{application.currentRound || "—"}</td>
                    <td className="td text-xs">{formatDate(application.appliedAt)}</td>
                    <td className="td">{application.offer?.ctc ? `${application.offer.ctc} LPA` : "—"}</td>
                    <td className="td text-right">
                      <button type="button" className="link" onClick={() => setSelected(application)}>
                        Open
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {selected ? (
        <ApplicationDrawer
          application={selected}
          isAdmin={isAdmin}
          isStudent={isStudent}
          onClose={() => setSelected(null)}
          onUpdated={updateSelected}
          onError={setError}
        />
      ) : null}
    </div>
  );
}

function ApplicationDrawer({ application, isAdmin, isStudent, onClose, onUpdated, onError }) {
  const drive = useAsync(() => api(`/drives/${application.driveId}`), [application.driveId]);
  const [round, setRound] = useState({
    roundName: application.currentRound || "",
    status: "cleared",
    score: "",
    remarks: "",
  });
  const [outcome, setOutcome] = useState({
    outcome: "selected",
    ctc: application.offer?.ctc ?? "",
    offerDate: new Date().toISOString().slice(0, 10),
  });
  const [busy, setBusy] = useState(false);

  async function submitRound(event) {
    event.preventDefault();
    setBusy(true);
    onError("");
    try {
      const updated = await api(`/applications/${application.id}/round`, {
        method: "PATCH",
        body: {
          roundName: round.roundName,
          status: round.status,
          score: round.score === "" ? null : Number(round.score),
          remarks: round.remarks || null,
        },
      });
      onUpdated(updated);
    } catch (err) {
      onError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function submitOutcome(event) {
    event.preventDefault();
    setBusy(true);
    onError("");
    try {
      const updated = await api(`/applications/${application.id}/outcome`, {
        method: "PATCH",
        body: {
          outcome: outcome.outcome,
          ctc: outcome.outcome === "selected" ? Number(outcome.ctc) : null,
          offerDate: outcome.outcome === "selected" ? outcome.offerDate : null,
        },
      });
      onUpdated(updated);
    } catch (err) {
      onError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function withdraw() {
    setBusy(true);
    onError("");
    try {
      const updated = await api(`/applications/${application.id}/outcome`, {
        method: "PATCH",
        body: { outcome: "withdrawn" },
      });
      onUpdated(updated);
    } catch (err) {
      onError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function openOfferLetter() {
    try {
      const result = await api(`/applications/${application.id}/offer-letter-url`);
      window.open(result.offerLetterUrl, "_blank", "noopener");
    } catch (err) {
      onError(err.message);
    }
  }

  async function uploadOfferLetter(event) {
    const file = event.target.files?.[0];
    if (!file) return;
    const form = new FormData();
    form.append("file", file);
    setBusy(true);
    try {
      await api(`/applications/${application.id}/offer-letter`, { method: "POST", body: form });
      onUpdated(application);
    } catch (err) {
      onError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <button type="button" className="absolute inset-0 bg-slate-900/30" aria-label="Close panel" onClick={onClose} />
      <aside className="relative flex h-full w-full max-w-xl flex-col overflow-y-auto bg-white shadow-2xl">
        <header className="sticky top-0 z-10 flex items-start justify-between gap-3 border-b border-slate-200 bg-white px-6 py-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Application</p>
            <h2 className="text-lg font-bold text-slate-900">{application.companyName}</h2>
            <p className="text-sm text-slate-500">
              {application.studentName} · {application.driveRole}
            </p>
          </div>
          <button type="button" className="rounded-lg p-2 text-slate-500 hover:bg-slate-100" onClick={onClose} aria-label="Close">
            <Icon name="close" />
          </button>
        </header>

        <div className="space-y-5 p-6">
          <div className="flex flex-wrap items-center gap-2">
            <StatusBadge status={application.status} />
            {application.currentRound ? <Badge tone="brand">Round: {application.currentRound}</Badge> : null}
            {application.offer?.ctc ? <Badge tone="green">{application.offer.ctc} LPA</Badge> : null}
          </div>

          <section>
            <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Round history</h3>
            {(application.roundResults || []).length === 0 ? (
              <p className="mt-2 text-sm text-slate-400">No rounds recorded yet.</p>
            ) : (
              <ol className="mt-2 space-y-2">
                {application.roundResults.map((result) => (
                  <li key={`${result.roundName}-${result.recordedAt}`} className="flex items-start gap-3 rounded-lg border border-slate-100 p-3">
                    <span className="mt-0.5 rounded-full bg-brand-50 p-1 text-brand-700">
                      <Icon name="check" className="h-3.5 w-3.5" />
                    </span>
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <p className="text-sm font-semibold text-slate-800">{result.roundName}</p>
                        <StatusBadge status={result.status} />
                      </div>
                      <p className="text-xs text-slate-500">
                        {result.score != null ? `Score ${result.score} · ` : ""}
                        {result.remarks || "No remarks"}
                        {result.recordedAt ? ` · ${formatDateTime(result.recordedAt)}` : ""}
                      </p>
                    </div>
                  </li>
                ))}
              </ol>
            )}
          </section>

          <section className="rounded-lg border border-slate-200 p-4">
            <h3 className="text-sm font-semibold text-slate-900">Offer</h3>
            <p className="mt-1 text-xs text-slate-500">
              Applied {formatDate(application.appliedAt)} · Updated {formatDateTime(application.updatedAt)}
            </p>
            <div className="mt-2 flex flex-wrap gap-2">
              {application.offer?.letterPath ? (
                <button type="button" className="btn-secondary" onClick={openOfferLetter}>
                  View offer letter
                </button>
              ) : isAdmin ? (
                <label className="btn-secondary cursor-pointer">
                  Upload offer letter
                  <input type="file" className="hidden" accept=".pdf" onChange={uploadOfferLetter} />
                </label>
              ) : (
                <p className="text-sm text-slate-400">No offer letter on file.</p>
              )}
            </div>
          </section>

          {isAdmin ? (
            <>
              <form onSubmit={submitRound} className="space-y-3 rounded-lg border border-slate-200 p-4">
                <h3 className="text-sm font-semibold text-slate-900">Record a round result</h3>
                <Field label="Round">
                  <select
                    className="input"
                    value={round.roundName}
                    onChange={(event) => setRound({ ...round, roundName: event.target.value })}
                    required
                  >
                    <option value="">Select a round</option>
                    {(drive.data?.rounds || []).map((item) => (
                      <option key={item.name} value={item.name}>
                        {item.name}
                      </option>
                    ))}
                  </select>
                </Field>
                <div className="grid grid-cols-2 gap-3">
                  <Field label="Result">
                    <select className="input" value={round.status} onChange={(event) => setRound({ ...round, status: event.target.value })}>
                      {["shortlisted", "cleared", "rejected", "absent"].map((status) => (
                        <option key={status} value={status}>
                          {titleCase(status)}
                        </option>
                      ))}
                    </select>
                  </Field>
                  <Field label="Score (optional)">
                    <input type="number" className="input" value={round.score} onChange={(event) => setRound({ ...round, score: event.target.value })} />
                  </Field>
                </div>
                <Field label="Remarks">
                  <input className="input" value={round.remarks} onChange={(event) => setRound({ ...round, remarks: event.target.value })} />
                </Field>
                <button type="submit" className="btn-primary" disabled={busy || !round.roundName}>
                  {busy ? "Saving…" : "Save round result"}
                </button>
              </form>

              <form onSubmit={submitOutcome} className="space-y-3 rounded-lg border border-slate-200 p-4">
                <h3 className="text-sm font-semibold text-slate-900">Record final outcome</h3>
                <div className="grid grid-cols-2 gap-3">
                  <Field label="Outcome">
                    <select className="input" value={outcome.outcome} onChange={(event) => setOutcome({ ...outcome, outcome: event.target.value })}>
                      <option value="selected">Selected</option>
                      <option value="rejected">Rejected</option>
                    </select>
                  </Field>
                  {outcome.outcome === "selected" ? (
                    <Field label="CTC (LPA)">
                      <input required type="number" step="0.1" min="0" className="input" value={outcome.ctc} onChange={(event) => setOutcome({ ...outcome, ctc: event.target.value })} />
                    </Field>
                  ) : null}
                </div>
                {outcome.outcome === "selected" ? (
                  <Field label="Offer date">
                    <input type="date" className="input" value={outcome.offerDate} onChange={(event) => setOutcome({ ...outcome, offerDate: event.target.value })} />
                  </Field>
                ) : null}
                <button type="submit" className="btn-primary" disabled={busy}>
                  {busy ? "Saving…" : "Save outcome"}
                </button>
                <p className="text-xs text-slate-400">
                  Selecting marks the student placed and locks further offers. Clear the lock from the
                  student profile to allow a dream offer.
                </p>
              </form>
            </>
          ) : null}

          {isStudent && application.status !== "withdrawn" ? (
            <button type="button" className="btn-danger" onClick={withdraw} disabled={busy}>
              Withdraw application
            </button>
          ) : null}
        </div>
      </aside>
    </div>
  );
}
