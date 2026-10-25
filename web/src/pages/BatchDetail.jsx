import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { api } from "../lib/api";
import { formatDate, pct, titleCase } from "../lib/format";
import { useAsync } from "../lib/useAsync";
import { Icon } from "../components/Icon";
import {
  BackLink,
  Badge,
  Card,
  CardHeader,
  EmptyState,
  ErrorBanner,
  Field,
  PageHeader,
  Progress,
  Spinner,
  StatusBadge,
  Tabs,
} from "../components/ui";

const TABS = [
  { id: "attendance", label: "Attendance" },
  { id: "assessments", label: "Assessments" },
  { id: "students", label: "Students" },
];

export default function BatchDetail() {
  const { batchId } = useParams();
  const { isStaff, isAdmin } = useAuth();
  const [tab, setTab] = useState("attendance");
  const batch = useAsync(() => api(`/batches/${batchId}`), [batchId]);
  const summary = useAsync(() => api(`/batches/${batchId}/attendance/summary`), [batchId]);
  const students = useAsync(() => api(`/batches/${batchId}/students`, { query: { limit: 100 } }), [batchId]);
  const sessions = useAsync(() => api(`/batches/${batchId}/sessions`, { query: { limit: 100 } }), [batchId]);
  const assessments = useAsync(() => api("/assessments", { query: { batchId, limit: 100 } }), [batchId]);
  const candidates = useAsync(
    () =>
      isAdmin && batch.data?.collegeId
        ? api("/students", { query: { limit: 100, collegeId: batch.data.collegeId } })
        : Promise.resolve(null),
    [isAdmin, batch.data?.collegeId]
  );

  if (batch.loading) return <Spinner label="Loading batch…" />;
  const data = batch.data;
  if (!data) {
    return (
      <div>
        <ErrorBanner error={batch.error} />
        <Card>
          <EmptyState title="Batch not found" body="It may have been archived, or you do not have access." />
        </Card>
      </div>
    );
  }

  return (
    <div>
      <div className="mb-4">
        <BackLink to="/batches">Batches</BackLink>
      </div>
      <PageHeader title={data.name} subtitle={`${data.course} · ${data.collegeName}`}>
        <StatusBadge status={data.status} />
        <Badge tone="brand">{data.studentCount ?? 0} students</Badge>
        <Badge tone="slate">Min attendance {pct(data.minAttendancePct, 0)}</Badge>
      </PageHeader>

      <ErrorBanner
        error={batch.error || summary.error || students.error || sessions.error || assessments.error}
      />

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <MiniStat label="Sessions" value={summary.data?.sessions ?? 0} />
        <MiniStat label="Average attendance" value={pct(summary.data?.averagePercentage)} />
        <MiniStat label="At risk" value={summary.data?.atRiskCount ?? 0} tone="rose" />
        <MiniStat
          label="Timeline"
          value={`${formatDate(data.startDate)} — ${formatDate(data.endDate)}`}
          small
        />
      </div>

      <div className="mt-6">
        <Tabs tabs={TABS} active={tab} onChange={setTab} />
      </div>

      <div className="mt-4">
        {tab === "attendance" ? (
          <AttendanceSection
            batchId={batchId}
            isStaff={isStaff}
            students={students.data?.items || []}
            sessions={sessions.data?.items || []}
            summary={summary.data}
            onChanged={() => {
              summary.reload();
              sessions.reload();
            }}
          />
        ) : null}
        {tab === "assessments" ? (
          <AssessmentsSection
            batchId={batchId}
            isStaff={isStaff}
            students={students.data?.items || []}
            assessments={assessments.data?.items || []}
            onChanged={() => assessments.reload()}
          />
        ) : null}
        {tab === "students" ? (
          <StudentsSection
            batchId={batchId}
            isAdmin={isAdmin}
            students={students.data?.items || []}
            studentsLoading={students.loading}
            candidates={candidates.data?.items || []}
            onChanged={() => {
              students.reload();
              batch.reload();
            }}
          />
        ) : null}
      </div>
    </div>
  );
}

function MiniStat({ label, value, tone = "brand", small = false }) {
  return (
    <Card className="p-4">
      <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">{label}</p>
      <p className={`mt-1 font-bold ${small ? "text-sm" : "text-xl"} ${tone === "rose" ? "text-rose-600" : "text-slate-900"}`}>
        {value}
      </p>
    </Card>
  );
}

function StudentsSection({ batchId, isAdmin, students, studentsLoading, candidates, onChanged }) {
  const [selected, setSelected] = useState([]);
  const [move, setMove] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const available = (candidates || []).filter((student) => student.batchId !== batchId);

  async function assign(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      if (!selected.length) throw new Error("Select at least one student.");
      await api(`/batches/${batchId}/students`, {
        method: "POST",
        body: { studentIds: selected, move },
      });
      setSelected([]);
      onChanged();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-5">
      {isAdmin ? (
        <Card>
          <CardHeader
            title="Assign students"
            subtitle="Move students into this batch; movement history is recorded"
          />
          <form onSubmit={assign} className="grid gap-4 p-5 md:grid-cols-3">
            <div className="md:col-span-2">
              <Field label="Students" hint="Ctrl/Cmd click to select multiple">
                <select
                  multiple
                  className="input min-h-[110px]"
                  value={selected}
                  onChange={(event) =>
                    setSelected(Array.from(event.target.selectedOptions, (option) => option.value))
                  }
                >
                  {available.map((student) => (
                    <option key={student.id} value={student.id}>
                      {student.name} · {student.rollNo || student.email}
                      {student.batchName ? ` (${student.batchName})` : ""}
                    </option>
                  ))}
                </select>
              </Field>
              {available.length === 0 ? (
                <p className="mt-2 text-xs text-slate-500">
                  No unassigned students in this college, or every student is already here.
                </p>
              ) : null}
            </div>
            <div className="flex flex-col justify-end gap-3">
              <label className="flex items-center gap-2 text-sm text-slate-600">
                <input
                  type="checkbox"
                  className="h-4 w-4 rounded border-slate-300 text-brand-600"
                  checked={move}
                  onChange={(event) => setMove(event.target.checked)}
                />
                Move from the current batch
              </label>
              <button type="submit" className="btn-primary" disabled={busy || selected.length === 0}>
                {busy ? "Assigning…" : `Assign ${selected.length || ""}`.trim()}
              </button>
              {error ? <p className="text-xs font-semibold text-rose-600">{error}</p> : null}
            </div>
          </form>
        </Card>
      ) : null}

      <Card>
        <CardHeader title="Enrolled students" subtitle="Open a profile to view readiness and edit details" />
        {studentsLoading ? (
          <Spinner />
        ) : (students || []).length === 0 ? (
          <EmptyState title="No students in this batch" body={isAdmin ? "Assign students above or from the People page." : undefined} />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[680px]">
              <thead className="bg-slate-50">
                <tr>
                  <th className="th">Student</th>
                  <th className="th">CGPA</th>
                  <th className="th">Attendance</th>
                  <th className="th">Readiness</th>
                  <th className="th">Status</th>
                  <th className="th" />
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {students.map((student) => (
                  <tr key={student.id} className="hover:bg-slate-50">
                    <td className="td">
                      <p className="font-semibold text-slate-900">{student.name}</p>
                      <p className="text-xs text-slate-500">{student.rollNo || student.email}</p>
                    </td>
                    <td className="td">{student.cgpa ?? "—"}</td>
                    <td className="td">{pct(student.attendancePct)}</td>
                    <td className="td">{Math.round(student.readinessScore || 0)}</td>
                    <td className="td">
                      <StatusBadge status={student.placementStatus} />
                    </td>
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
        )}
      </Card>
    </div>
  );
}


function AttendanceSection({ batchId, isStaff, students, sessions, summary, onChanged }) {
  const [showSession, setShowSession] = useState(false);
  const [marking, setMarking] = useState(null);
  const [statuses, setStatuses] = useState({});
  const [form, setForm] = useState({ date: new Date().toISOString().slice(0, 10), topic: "", durationMinutes: 90 });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function createSession(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api(`/batches/${batchId}/sessions`, {
        method: "POST",
        body: { date: form.date, topic: form.topic, durationMinutes: Number(form.durationMinutes) },
      });
      setShowSession(false);
      setForm({ ...form, topic: "" });
      onChanged();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function saveAttendance(sessionId) {
    setBusy(true);
    setError("");
    try {
      await api(`/sessions/${sessionId}/attendance`, {
        method: "POST",
        body: {
          records: students.map((student) => ({
            studentId: student.id,
            status: statuses[student.id] || "present",
          })),
        },
      });
      setMarking(null);
      onChanged();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid gap-5 lg:grid-cols-3">
      <div className="space-y-5 lg:col-span-2">
        <Card>
          <CardHeader
            title="Sessions"
            subtitle="Create a session, then mark the batch"
            action={
              isStaff ? (
                <button type="button" className="btn-secondary" onClick={() => setShowSession(!showSession)}>
                  {showSession ? "Close" : "New session"}
                </button>
              ) : null
            }
          />
          {error ? <p className="px-5 pt-3 text-sm font-semibold text-rose-600">{error}</p> : null}
          {showSession ? (
            <form onSubmit={createSession} className="grid gap-3 border-b border-slate-100 p-5 sm:grid-cols-3">
              <Field label="Date">
                <input required type="date" className="input" value={form.date} onChange={(event) => setForm({ ...form, date: event.target.value })} />
              </Field>
              <Field label="Topic">
                <input required className="input" value={form.topic} onChange={(event) => setForm({ ...form, topic: event.target.value })} />
              </Field>
              <div className="flex items-end gap-2">
                <Field label="Minutes">
                  <input type="number" className="input" value={form.durationMinutes} onChange={(event) => setForm({ ...form, durationMinutes: event.target.value })} />
                </Field>
                <button type="submit" className="btn-primary" disabled={busy || !students.length}>
                  Add
                </button>
              </div>
            </form>
          ) : null}

          {sessions.length === 0 ? (
            <EmptyState title="No sessions yet" body={isStaff ? "Create the first session to start tracking attendance." : "Attendance sessions will appear here."} />
          ) : (
            <div className="divide-y divide-slate-100">
              {sessions.map((session) => (
                <div key={session.id} className="px-5 py-3">
                  <div className="flex flex-wrap items-center gap-3">
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-semibold text-slate-900">{session.topic}</p>
                      <p className="text-xs text-slate-500">
                        {formatDate(session.date)} · {session.trainerName || "Trainer"} ·{" "}
                        {session.presentCount}/{session.totalCount} credited
                      </p>
                    </div>
                    {session.marked ? <Badge tone="green">Marked</Badge> : <Badge tone="amber">Unmarked</Badge>}
                    {isStaff ? (
                      <button
                        type="button"
                        className="btn-secondary px-3 py-1.5 text-xs"
                        onClick={() => {
                          setMarking(marking === session.id ? null : session.id);
                          setStatuses(
                            Object.fromEntries(students.map((student) => [student.id, "present"]))
                          );
                        }}
                      >
                        {marking === session.id ? "Cancel" : session.marked ? "Update marks" : "Mark attendance"}
                      </button>
                    ) : null}
                  </div>
                  {marking === session.id ? (
                    <div className="mt-3 rounded-lg border border-slate-200 bg-slate-50 p-3">
                      <div className="grid gap-2 sm:grid-cols-2">
                        {students.map((student) => (
                          <label key={student.id} className="flex items-center justify-between gap-2 rounded-md bg-white px-3 py-2 text-sm">
                            <span className="truncate">{student.name}</span>
                            <select
                              className="rounded-md border border-slate-300 px-2 py-1 text-xs"
                              value={statuses[student.id] || "present"}
                              onChange={(event) =>
                                setStatuses({ ...statuses, [student.id]: event.target.value })
                              }
                            >
                              {["present", "absent", "late", "excused"].map((status) => (
                                <option key={status} value={status}>
                                  {titleCase(status)}
                                </option>
                              ))}
                            </select>
                          </label>
                        ))}
                      </div>
                      <button
                        type="button"
                        className="btn-primary mt-3"
                        disabled={busy || !students.length}
                        onClick={() => saveAttendance(session.id)}
                      >
                        {busy ? "Saving…" : "Save attendance"}
                      </button>
                    </div>
                  ) : null}
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>

      <Card>
        <CardHeader title="Attendance summary" subtitle="Per student" />
        {!summary ? (
          <Spinner />
        ) : (summary.students || []).length === 0 ? (
          <EmptyState title="No attendance data" />
        ) : (
          <div className="divide-y divide-slate-100">
            {summary.students.map((row) => (
              <div key={row.studentId} className="px-5 py-3">
                <div className="flex items-center justify-between text-sm">
                  <span className="font-medium text-slate-800">{row.studentName}</span>
                  <span className={row.atRisk ? "font-semibold text-rose-600" : "text-slate-600"}>
                    {pct(row.percentage)}
                  </span>
                </div>
                <Progress className="mt-1.5" value={row.percentage} tone={row.atRisk ? "rose" : "green"} />
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}

function AssessmentsSection({ batchId, isStaff, students, assessments, onChanged }) {
  const [showCreate, setShowCreate] = useState(false);
  const [scoring, setScoring] = useState(null);
  const [marks, setMarks] = useState({});
  const [form, setForm] = useState({
    title: "",
    type: "assignment",
    maxMarks: 100,
    weightage: 1,
    date: new Date().toISOString().slice(0, 10),
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function createAssessment(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api("/assessments", {
        method: "POST",
        body: {
          batchId,
          title: form.title,
          type: form.type,
          maxMarks: Number(form.maxMarks),
          weightage: Number(form.weightage),
          date: form.date,
        },
      });
      setShowCreate(false);
      setForm({ ...form, title: "" });
      onChanged();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function saveScores(assessmentId) {
    setBusy(true);
    setError("");
    try {
      const records = students
        .filter((student) => marks[student.id] !== undefined && marks[student.id] !== "")
        .map((student) => ({ studentId: student.id, marks: Number(marks[student.id]) }));
      if (!records.length) throw new Error("Enter at least one score.");
      await api(`/assessments/${assessmentId}/scores`, { method: "POST", body: { records } });
      setScoring(null);
      setMarks({});
      onChanged();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <CardHeader
        title="Assessments"
        subtitle="Scores are idempotent per student"
        action={
          isStaff ? (
            <button type="button" className="btn-secondary" onClick={() => setShowCreate(!showCreate)}>
              {showCreate ? "Close" : "New assessment"}
            </button>
          ) : null
        }
      />
      {error ? <p className="px-5 pt-3 text-sm font-semibold text-rose-600">{error}</p> : null}
      {showCreate ? (
        <form onSubmit={createAssessment} className="grid gap-3 border-b border-slate-100 p-5 md:grid-cols-5">
          <div className="md:col-span-2">
            <Field label="Title">
              <input required className="input" value={form.title} onChange={(event) => setForm({ ...form, title: event.target.value })} />
            </Field>
          </div>
          <Field label="Type">
            <select className="input" value={form.type} onChange={(event) => setForm({ ...form, type: event.target.value })}>
              {["quiz", "assignment", "mock_test", "mock_interview", "aptitude"].map((type) => (
                <option key={type} value={type}>
                  {titleCase(type)}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Max marks">
            <input type="number" min="1" className="input" value={form.maxMarks} onChange={(event) => setForm({ ...form, maxMarks: event.target.value })} />
          </Field>
          <div className="flex items-end">
            <button type="submit" className="btn-primary w-full" disabled={busy}>
              Create
            </button>
          </div>
        </form>
      ) : null}

      {assessments.length === 0 ? (
        <EmptyState title="No assessments yet" />
      ) : (
        <div className="divide-y divide-slate-100">
          {assessments.map((assessment) => (
            <div key={assessment.id} className="px-5 py-4">
              <div className="flex flex-wrap items-center gap-3">
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-semibold text-slate-900">{assessment.title}</p>
                  <p className="text-xs text-slate-500">
                    {titleCase(assessment.type)} · {formatDate(assessment.date)} · max {assessment.maxMarks} ·{" "}
                    {assessment.scoredCount} scored
                  </p>
                </div>
                {isStaff ? (
                  <button
                    type="button"
                    className="btn-secondary px-3 py-1.5 text-xs"
                    onClick={() => {
                      setScoring(scoring === assessment.id ? null : assessment.id);
                      setMarks({});
                    }}
                  >
                    {scoring === assessment.id ? "Cancel" : "Record scores"}
                  </button>
                ) : null}
              </div>
              {scoring === assessment.id ? (
                <div className="mt-3 rounded-lg border border-slate-200 bg-slate-50 p-3">
                  <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                    {students.map((student) => (
                      <label key={student.id} className="flex items-center justify-between gap-2 rounded-md bg-white px-3 py-2 text-sm">
                        <span className="truncate">{student.name}</span>
                        <input
                          type="number"
                          min="0"
                          max={assessment.maxMarks}
                          step="0.5"
                          placeholder="—"
                          className="w-20 rounded-md border border-slate-300 px-2 py-1 text-xs"
                          value={marks[student.id] ?? ""}
                          onChange={(event) => setMarks({ ...marks, [student.id]: event.target.value })}
                        />
                      </label>
                    ))}
                  </div>
                  <button type="button" className="btn-primary mt-3" disabled={busy} onClick={() => saveScores(assessment.id)}>
                    {busy ? "Saving…" : "Save scores"}
                  </button>
                </div>
              ) : null}
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}
