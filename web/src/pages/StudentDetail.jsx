import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { api } from "../lib/api";
import { formatDate, formatDateTime, pct, titleCase } from "../lib/format";
import { useAsync } from "../lib/useAsync";
import { Icon } from "../components/Icon";
import {
  Avatar,
  BackLink,
  Badge,
  Card,
  CardHeader,
  EmptyState,
  ErrorBanner,
  Field,
  MiniBars,
  PageHeader,
  Progress,
  ReadinessRing,
  Spinner,
  StatusBadge,
  Tabs,
} from "../components/ui";

const TABS = [
  { id: "overview", label: "Overview" },
  { id: "attendance", label: "Attendance" },
  { id: "scores", label: "Assessments" },
  { id: "feedback", label: "Feedback" },
  { id: "applications", label: "Applications" },
];

export default function StudentDetail({ studentId: propId }) {
  const params = useParams();
  const studentId = propId || params.studentId;
  const { me, isStaff, isAdmin, isStudent } = useAuth();
  const [tab, setTab] = useState("overview");
  const profile = useAsync(() => api(`/students/${studentId}`), [studentId]);
  const analytics = useAsync(() => api(`/analytics/student/${studentId}`), [studentId]);
  const attendance = useAsync(() => api(`/students/${studentId}/attendance`), [studentId]);
  const scores = useAsync(() => api(`/students/${studentId}/scores`), [studentId]);
  const feedback = useAsync(() => api(`/students/${studentId}/feedback`), [studentId]);
  const applications = useAsync(
    () => api("/applications", { query: { studentId, limit: 50 } }),
    [studentId]
  );

  if (profile.loading) return <Spinner label="Loading student profile…" />;

  const student = profile.data;
  const metrics = analytics.data;
  if (!student) {
    return (
      <div>
        <ErrorBanner error={profile.error} />
        <Card>
          <EmptyState title="Student not found" body="It may have been removed, or you do not have access." />
        </Card>
      </div>
    );
  }

  const mine = isStudent && student.uid === me.uid;

  return (
    <div>
      <div className="mb-4">
        <BackLink to={isStudent ? "/" : "/students"}>{isStudent ? "Dashboard" : "Students"}</BackLink>
      </div>
      <PageHeader
        title={student.name}
        subtitle={`${student.collegeName || "College"} · ${student.batchName || "No batch"} · ${student.email}`}
      >
        {student.resumePath ? <ResumeButton studentId={studentId} /> : null}
        {mine || isAdmin ? (
          <label className="btn-secondary cursor-pointer">
            <Icon name="reports" className="h-4 w-4" />
            Upload resume
            <input
              type="file"
              className="hidden"
              accept=".pdf,.doc,.docx"
              onChange={async (event) => {
                const file = event.target.files?.[0];
                if (!file) return;
                const form = new FormData();
                form.append("file", file);
                try {
                  await api(`/students/${studentId}/resume`, { method: "POST", body: form });
                  profile.reload();
                } catch (err) {
                  window.alert(err.message);
                }
              }}
            />
          </label>
        ) : null}
      </PageHeader>

      <ErrorBanner
        error={
          profile.error ||
          analytics.error ||
          attendance.error ||
          scores.error ||
          feedback.error ||
          applications.error
        }
      />

      <div className="grid gap-5 lg:grid-cols-3">
        <Card className="p-5">
          <div className="flex items-center gap-4">
            <Avatar name={student.name} size="lg" />
            <div className="min-w-0">
              <p className="truncate text-lg font-bold text-slate-900">{student.name}</p>
              <p className="text-sm text-slate-500">{student.rollNo || "Roll number not set"}</p>
              <div className="mt-1 flex flex-wrap gap-1">
                <StatusBadge status={student.placementStatus} />
                {student.atRisk ? <Badge tone="rose">at risk</Badge> : null}
              </div>
            </div>
          </div>
          <dl className="mt-5 grid grid-cols-2 gap-3 text-sm">
            <Meta label="Branch" value={student.branch || "—"} />
            <Meta label="Degree" value={student.degree || "—"} />
            <Meta label="Graduation" value={student.gradYear || "—"} />
            <Meta label="CGPA" value={student.cgpa ?? "—"} />
            <Meta label="Phone" value={student.phone || "—"} />
            <Meta label="Profile score" value={`${student.profileScore}/100`} />
          </dl>
          <div className="mt-4 flex flex-wrap gap-1.5">
            {(student.skills || []).map((skill) => (
              <Badge key={skill} tone="brand">
                {skill}
              </Badge>
            ))}
            {(student.skills || []).length === 0 ? (
              <p className="text-xs text-slate-400">No skills added yet.</p>
            ) : null}
          </div>
          {student.links?.github || student.links?.linkedin ? (
            <div className="mt-4 flex gap-3 text-sm">
              {student.links.github ? (
                <a className="link" href={student.links.github} target="_blank" rel="noreferrer">
                  GitHub
                </a>
              ) : null}
              {student.links.linkedin ? (
                <a className="link" href={student.links.linkedin} target="_blank" rel="noreferrer">
                  LinkedIn
                </a>
              ) : null}
            </div>
          ) : null}
          {student.placedCompany ? (
            <div className="mt-4 rounded-lg bg-emerald-50 p-3 text-sm text-emerald-800">
              Placed at <strong>{student.placedCompany}</strong> · {student.placedCtc} LPA
            </div>
          ) : null}
        </Card>

        <Card className="p-5">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Readiness</p>
          <div className="mt-3 flex items-center gap-5">
            <ReadinessRing value={metrics?.readinessScore ?? student.readinessScore} size={112} />
            <div className="flex-1 space-y-3">
              <Metric label="Attendance" value={metrics?.attendancePct ?? student.attendancePct} />
              <Metric label="Assessments" value={metrics?.assessmentAvg ?? student.assessmentAvg} />
              <Metric label="Interviews" value={metrics?.interviewAvg ?? student.interviewAvg} />
              <Metric label="Profile" value={metrics?.profileScore ?? student.profileScore} max={100} />
            </div>
          </div>
          <div className="mt-4 flex items-center justify-between rounded-lg bg-slate-50 px-3 py-2 text-xs text-slate-600">
            <span>Rank band</span>
            <Badge tone="brand">{titleCase(metrics?.rankBand || "unranked")}</Badge>
          </div>
        </Card>

        <Card>
          <CardHeader title="Edit profile" subtitle={mine ? "Update your own details" : "Staff edit"} />
          <ProfileForm
            student={student}
            mine={mine}
            isAdmin={isAdmin}
            isStaff={isStaff}
            onSaved={() => {
              profile.reload();
              analytics.reload();
            }}
          />
        </Card>
      </div>

      <div className="mt-6">
        <Tabs tabs={TABS} active={tab} onChange={setTab} />
      </div>

      <div className="mt-4">
        {tab === "overview" ? (
          <div className="grid gap-5 lg:grid-cols-2">
            <Card>
              <CardHeader title="Attendance trend" subtitle="Credited share by session date" />
              <div className="p-5">
                <MiniBars data={metrics?.attendanceTrend || []} />
              </div>
            </Card>
            <Card>
              <CardHeader title="Assessment trend" subtitle="Percentage per assessment" />
              <div className="p-5">
                <MiniBars data={metrics?.scoreTrend || []} />
              </div>
            </Card>
            <Card className="lg:col-span-2">
              <CardHeader title="Projects and certifications" />
              <div className="grid gap-5 p-5 md:grid-cols-2">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Projects</p>
                  {(student.projects || []).length === 0 ? (
                    <p className="mt-2 text-sm text-slate-400">No projects added.</p>
                  ) : (
                    <ul className="mt-2 space-y-2">
                      {student.projects.map((project) => (
                        <li key={project.title} className="rounded-lg border border-slate-100 p-3">
                          <p className="text-sm font-semibold text-slate-800">{project.title}</p>
                          {project.description ? (
                            <p className="mt-0.5 text-xs text-slate-500">{project.description}</p>
                          ) : null}
                          <p className="mt-1 text-xs text-slate-400">{(project.tech || []).join(" · ")}</p>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Certifications</p>
                  {(student.certifications || []).length === 0 ? (
                    <p className="mt-2 text-sm text-slate-400">No certifications added.</p>
                  ) : (
                    <ul className="mt-2 space-y-2">
                      {student.certifications.map((cert) => (
                        <li key={cert.name} className="rounded-lg border border-slate-100 p-3">
                          <p className="text-sm font-semibold text-slate-800">{cert.name}</p>
                          <p className="text-xs text-slate-500">
                            {[cert.issuer, cert.year].filter(Boolean).join(" · ")}
                          </p>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              </div>
            </Card>
          </div>
        ) : null}

        {tab === "attendance" ? <AttendanceTab data={attendance.data} /> : null}
        {tab === "scores" ? <ScoresTab data={scores.data} /> : null}
        {tab === "feedback" ? (
          <FeedbackTab
            items={feedback.data}
            studentId={studentId}
            canCreate={isStaff}
            onCreated={() => {
              feedback.reload();
              analytics.reload();
            }}
          />
        ) : null}
        {tab === "applications" ? <ApplicationsTab data={applications.data} /> : null}
      </div>
    </div>
  );
}

function Meta({ label, value }) {
  return (
    <div>
      <dt className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">{label}</dt>
      <dd className="mt-0.5 text-sm text-slate-700">{value}</dd>
    </div>
  );
}

function Metric({ label, value, max = 100 }) {
  return (
    <div>
      <div className="mb-1 flex justify-between text-xs">
        <span className="text-slate-600">{label}</span>
        <span className="font-semibold text-slate-800">{pct(value)}</span>
      </div>
      <Progress value={(Number(value) / max) * 100} />
    </div>
  );
}

function ResumeButton({ studentId }) {
  return (
    <button
      type="button"
      className="btn-secondary"
      onClick={async () => {
        try {
          const result = await api(`/students/${studentId}/resume-url`);
          window.open(result.resumeUrl, "_blank", "noopener");
        } catch (err) {
          window.alert(err.message);
        }
      }}
    >
      <Icon name="reports" className="h-4 w-4" />
      Resume
    </button>
  );
}

function ProfileForm({ student, mine, isAdmin, isStaff, onSaved }) {
  const [form, setForm] = useState({
    name: student.name || "",
    phone: student.phone || "",
    skills: (student.skills || []).join(", "),
    rollNo: student.rollNo || "",
    degree: student.degree || "",
    branch: student.branch || "",
    gradYear: student.gradYear || "",
    cgpa: student.cgpa ?? "",
    placementStatus: student.placementStatus || "unplaced",
    placementLocked: Boolean(student.placementLocked),
  });
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    setForm({
      name: student.name || "",
      phone: student.phone || "",
      skills: (student.skills || []).join(", "),
      rollNo: student.rollNo || "",
      degree: student.degree || "",
      branch: student.branch || "",
      gradYear: student.gradYear || "",
      cgpa: student.cgpa ?? "",
      placementStatus: student.placementStatus || "unplaced",
      placementLocked: Boolean(student.placementLocked),
    });
  }, [student]);

  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setMessage("");
    const payload = {
      name: form.name,
      phone: form.phone || null,
      skills: form.skills.split(",").map((item) => item.trim()).filter(Boolean),
    };
    if (isStaff) {
      payload.rollNo = form.rollNo || null;
      payload.degree = form.degree || null;
      payload.branch = form.branch || null;
      payload.gradYear = form.gradYear ? Number(form.gradYear) : null;
      payload.cgpa = form.cgpa === "" ? null : Number(form.cgpa);
    }
    if (isAdmin) {
      payload.placementStatus = form.placementStatus;
      payload.placementLocked = form.placementLocked;
    }
    try {
      await api(`/students/${student.id}`, { method: "PATCH", body: payload });
      setMessage("Profile saved.");
      onSaved();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-3 p-5">
      <Field label="Name">
        <input className="input" value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} />
      </Field>
      <Field label="Phone">
        <input className="input" value={form.phone} onChange={(event) => setForm({ ...form, phone: event.target.value })} />
      </Field>
      <Field label="Skills" hint="Comma separated">
        <input className="input" value={form.skills} onChange={(event) => setForm({ ...form, skills: event.target.value })} />
      </Field>
      {isStaff ? (
        <div className="grid grid-cols-2 gap-3">
          <Field label="Roll number">
            <input className="input" value={form.rollNo} onChange={(event) => setForm({ ...form, rollNo: event.target.value })} />
          </Field>
          <Field label="CGPA">
            <input
              type="number"
              step="0.01"
              min="0"
              max="10"
              className="input"
              value={form.cgpa}
              onChange={(event) => setForm({ ...form, cgpa: event.target.value })}
            />
          </Field>
          <Field label="Branch">
            <input className="input" value={form.branch} onChange={(event) => setForm({ ...form, branch: event.target.value })} />
          </Field>
          <Field label="Graduation year">
            <input
              type="number"
              className="input"
              value={form.gradYear}
              onChange={(event) => setForm({ ...form, gradYear: event.target.value })}
            />
          </Field>
        </div>
      ) : null}
      {isAdmin ? (
        <>
          <Field label="Placement status">
            <select
              className="input"
              value={form.placementStatus}
              onChange={(event) => setForm({ ...form, placementStatus: event.target.value })}
            >
              {["unplaced", "in_process", "placed", "opted_out"].map((status) => (
                <option key={status} value={status}>
                  {titleCase(status)}
                </option>
              ))}
            </select>
          </Field>
          <label className="flex items-center gap-2 text-sm text-slate-600">
            <input
              type="checkbox"
              className="h-4 w-4 rounded border-slate-300 text-brand-600"
              checked={form.placementLocked}
              onChange={(event) => setForm({ ...form, placementLocked: event.target.checked })}
            />
            Lock further offers (clear to allow a dream offer)
          </label>
        </>
      ) : null}
      {message ? <p className="text-xs font-semibold text-emerald-600">{message}</p> : null}
      {error ? <p className="text-xs font-semibold text-rose-600">{error}</p> : null}
      <button type="submit" className="btn-primary w-full" disabled={busy}>
        {busy ? "Saving…" : "Save changes"}
      </button>
    </form>
  );
}

function AttendanceTab({ data }) {
  if (!data) return <Spinner />;
  return (
    <div className="grid gap-5 lg:grid-cols-3">
      <Card className="p-5">
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Summary</p>
        <div className="mt-4 grid grid-cols-2 gap-3 text-center">
          {[
            ["Present", data.present, "green"],
            ["Absent", data.absent, "rose"],
            ["Late", data.late, "amber"],
            ["Excused", data.excused, "blue"],
          ].map(([label, value, tone]) => (
            <div key={label} className="rounded-lg bg-slate-50 p-3">
              <p className="text-xl font-bold text-slate-900">{value}</p>
              <Badge tone={tone}>{label}</Badge>
            </div>
          ))}
        </div>
        <div className="mt-4">
          <div className="mb-1 flex justify-between text-sm">
            <span className="text-slate-600">Attendance</span>
            <span className="font-semibold">{pct(data.percentage)}</span>
          </div>
          <Progress value={data.percentage} tone={data.atRisk ? "rose" : "green"} />
          <p className="mt-2 text-xs text-slate-500">
            Threshold {pct(data.threshold)} · {data.atRisk ? "Below threshold" : "Above threshold"}
          </p>
        </div>
      </Card>
      <Card className="lg:col-span-2">
        <CardHeader title="Session history" subtitle="Most recent first" />
        {data.history?.length ? (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[520px]">
              <thead className="bg-slate-50">
                <tr>
                  <th className="th">Date</th>
                  <th className="th">Topic</th>
                  <th className="th">Status</th>
                  <th className="th">Remarks</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {data.history.map((row) => (
                  <tr key={row.sessionId}>
                    <td className="td">{formatDate(row.date)}</td>
                    <td className="td">{row.topic}</td>
                    <td className="td">
                      <StatusBadge status={row.status} />
                    </td>
                    <td className="td text-slate-500">{row.remarks || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState title="No attendance yet" body="Sessions marked by trainers will appear here." />
        )}
      </Card>
    </div>
  );
}

function ScoresTab({ data }) {
  if (!data) return <Spinner />;
  return (
    <Card>
      <CardHeader
        title="Assessment scores"
        subtitle={`Weighted average ${pct(data.overallAverage)}`}
      />
      {data.items?.length ? (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[640px]">
            <thead className="bg-slate-50">
              <tr>
                <th className="th">Assessment</th>
                <th className="th">Type</th>
                <th className="th">Date</th>
                <th className="th">Marks</th>
                <th className="th">Percentage</th>
                <th className="th">Class avg</th>
                <th className="th">Rank band</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {data.items.map((item) => (
                <tr key={item.assessmentId}>
                  <td className="td font-semibold text-slate-900">{item.title}</td>
                  <td className="td">{titleCase(item.type)}</td>
                  <td className="td">{formatDate(item.date)}</td>
                  <td className="td">
                    {item.marks}/{item.maxMarks}
                  </td>
                  <td className="td">{pct(item.percentage)}</td>
                  <td className="td">{pct(item.classAverage)}</td>
                  <td className="td">
                    <Badge tone="brand">{titleCase(item.rankBand)}</Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <EmptyState title="No scores recorded" body="Assessment scores appear after trainers publish them." />
      )}
    </Card>
  );
}

function FeedbackTab({ items = [], studentId, canCreate, onCreated }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="space-y-4">
      {canCreate ? (
        <Card>
          <CardHeader
            title="Interview feedback"
            subtitle="Structured feedback updates readiness and notifies the student"
            action={
              <button type="button" className="btn-secondary" onClick={() => setOpen(!open)}>
                {open ? "Close" : "Add feedback"}
              </button>
            }
          />
          {open ? <FeedbackForm studentId={studentId} onCreated={onCreated} /> : null}
        </Card>
      ) : null}

      {(items || []).length === 0 ? (
        <Card>
          <EmptyState title="No interview feedback yet" body="Mock and real interview feedback appears here." />
        </Card>
      ) : (
        (items || []).map((item) => (
          <Card key={item.id} className="p-5">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="text-sm font-semibold text-slate-900">
                  {titleCase(item.interviewType)} interview · {formatDate(item.date)}
                </p>
                <p className="text-xs text-slate-500">
                  {item.givenByName || item.givenBy} · {formatDateTime(item.createdAt)}
                </p>
              </div>
              <div className="flex items-center gap-2">
                <Badge tone="brand">{item.averageRating?.toFixed?.(2) ?? item.averageRating}/5</Badge>
                <Badge tone={item.recommendation === "no" ? "rose" : "green"}>
                  {titleCase(item.recommendation)}
                </Badge>
              </div>
            </div>
            <div className="mt-3 grid gap-2 sm:grid-cols-4">
              {[
                ["Technical", item.ratings?.technical],
                ["Communication", item.ratings?.communication],
                ["Problem solving", item.ratings?.problemSolving],
                ["Attitude", item.ratings?.attitude],
              ].map(([label, value]) => (
                <div key={label} className="rounded-lg bg-slate-50 px-3 py-2">
                  <p className="text-[11px] text-slate-500">{label}</p>
                  <p className="text-sm font-semibold text-slate-800">{value}/5</p>
                </div>
              ))}
            </div>
            <div className="mt-3 grid gap-3 text-sm sm:grid-cols-2">
              {item.strengths ? (
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wide text-emerald-600">Strengths</p>
                  <p className="mt-1 text-slate-700">{item.strengths}</p>
                </div>
              ) : null}
              {item.improvements ? (
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wide text-amber-600">Improvements</p>
                  <p className="mt-1 text-slate-700">{item.improvements}</p>
                </div>
              ) : null}
            </div>
            {item.internalNotes ? (
              <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
                <p className="text-xs font-semibold uppercase tracking-wide">Internal notes (staff only)</p>
                <p className="mt-1">{item.internalNotes}</p>
              </div>
            ) : null}
          </Card>
        ))
      )}
    </div>
  );
}

function FeedbackForm({ studentId, onCreated }) {
  const today = new Date().toISOString().slice(0, 10);
  const [form, setForm] = useState({
    interviewType: "mock",
    date: today,
    technical: 3,
    communication: 3,
    problemSolving: 3,
    attitude: 3,
    recommendation: "maybe",
    strengths: "",
    improvements: "",
    internalNotes: "",
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api("/feedback", {
        method: "POST",
        body: {
          studentId,
          interviewType: form.interviewType,
          date: form.date,
          ratings: {
            technical: Number(form.technical),
            communication: Number(form.communication),
            problemSolving: Number(form.problemSolving),
            attitude: Number(form.attitude),
          },
          recommendation: form.recommendation,
          strengths: form.strengths || null,
          improvements: form.improvements || null,
          internalNotes: form.internalNotes || null,
        },
      });
      onCreated();
      setBusy(false);
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="grid gap-4 border-t border-slate-100 p-5 md:grid-cols-2">
      <Field label="Interview type">
        <select
          className="input"
          value={form.interviewType}
          onChange={(event) => setForm({ ...form, interviewType: event.target.value })}
        >
          <option value="mock">Mock</option>
          <option value="real">Real</option>
        </select>
      </Field>
      <Field label="Date">
        <input type="date" className="input" value={form.date} onChange={(event) => setForm({ ...form, date: event.target.value })} />
      </Field>
      {[
        ["technical", "Technical"],
        ["communication", "Communication"],
        ["problemSolving", "Problem solving"],
        ["attitude", "Attitude"],
      ].map(([key, label]) => (
        <Field key={key} label={`${label} rating`}>
          <select
            className="input"
            value={form[key]}
            onChange={(event) => setForm({ ...form, [key]: event.target.value })}
          >
            {[1, 2, 3, 4, 5].map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
        </Field>
      ))}
      <Field label="Recommendation">
        <select
          className="input"
          value={form.recommendation}
          onChange={(event) => setForm({ ...form, recommendation: event.target.value })}
        >
          {["strong_yes", "yes", "maybe", "no"].map((value) => (
            <option key={value} value={value}>
              {titleCase(value)}
            </option>
          ))}
        </select>
      </Field>
      <div className="md:col-span-2">
        <Field label="Strengths">
          <textarea className="input" rows={2} value={form.strengths} onChange={(event) => setForm({ ...form, strengths: event.target.value })} />
        </Field>
      </div>
      <div className="md:col-span-2">
        <Field label="Improvements">
          <textarea className="input" rows={2} value={form.improvements} onChange={(event) => setForm({ ...form, improvements: event.target.value })} />
        </Field>
      </div>
      <div className="md:col-span-2">
        <Field label="Internal notes" hint="Never shown to students">
          <textarea className="input" rows={2} value={form.internalNotes} onChange={(event) => setForm({ ...form, internalNotes: event.target.value })} />
        </Field>
      </div>
      {error ? <p className="text-sm font-semibold text-rose-600 md:col-span-2">{error}</p> : null}
      <div className="md:col-span-2">
        <button type="submit" className="btn-primary" disabled={busy}>
          {busy ? "Saving…" : "Save feedback"}
        </button>
      </div>
    </form>
  );
}

function ApplicationsTab({ data }) {
  if (!data) return <Spinner />;
  return (
    <Card>
      <CardHeader title="Applications" subtitle="Drive pipeline for this student" />
      {data.items?.length ? (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[620px]">
            <thead className="bg-slate-50">
              <tr>
                <th className="th">Company</th>
                <th className="th">Role</th>
                <th className="th">Status</th>
                <th className="th">Current round</th>
                <th className="th">Applied</th>
                <th className="th">Offer</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {data.items.map((application) => (
                <tr key={application.id}>
                  <td className="td font-semibold text-slate-900">{application.companyName}</td>
                  <td className="td">{application.driveRole}</td>
                  <td className="td">
                    <StatusBadge status={application.status} />
                  </td>
                  <td className="td">{application.currentRound || "—"}</td>
                  <td className="td">{formatDate(application.appliedAt)}</td>
                  <td className="td">{application.offer?.ctc ? `${application.offer.ctc} LPA` : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <EmptyState title="No applications yet" body="Browse drives to apply." action={<Link to="/drives" className="btn-primary mt-2">Browse drives</Link>} />
      )}
    </Card>
  );
}
