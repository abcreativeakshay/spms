import { useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { api } from "../lib/api";
import { formatDate, number, pct, titleCase } from "../lib/format";
import { useAsync } from "../lib/useAsync";
import { Icon } from "../components/Icon";
import {
  Avatar,
  Badge,
  Card,
  CardHeader,
  EmptyState,
  ErrorBanner,
  MiniBars,
  PageHeader,
  Progress,
  ReadinessRing,
  Spinner,
  StatCard,
  StatusBadge,
} from "../components/ui";

export default function Dashboard() {
  const { me, isStudent, isAdmin } = useAuth();
  if (isStudent) return <StudentDashboard me={me} />;
  if (isAdmin) return <AdminDashboard me={me} />;
  return <TrainerDashboard me={me} />;
}

function StudentDashboard({ me }) {
  const studentId = me.student?.id;
  const profile = useAsync(() => api(`/students/${studentId}`), [studentId]);
  const analytics = useAsync(() => api(`/analytics/student/${studentId}`), [studentId]);
  const drives = useAsync(() => api("/drives", { query: { limit: 5 } }), []);
  const student = profile.data;
  const metrics = analytics.data;

  if (profile.loading || analytics.loading) return <Spinner label="Loading your dashboard…" />;

  return (
    <div>
      <PageHeader
        title={`Welcome back, ${me.name.split(" ")[0]}`}
        subtitle={
          student
            ? `${student.collegeName || "College"} · ${student.batchName || "No batch"} · ${student.rollNo || "Roll number not set"}`
            : "Your placement workspace"
        }
      >
        <Link to="/profile" className="btn-secondary">
          <Icon name="user" className="h-4 w-4" />
          Edit profile
        </Link>
        <Link to="/drives" className="btn-primary">
          Browse drives
        </Link>
      </PageHeader>

      <ErrorBanner error={profile.error || analytics.error || drives.error} />

      <div className="grid gap-5 lg:grid-cols-3">
        <Card className="p-6 lg:col-span-1">
          <div className="flex items-start justify-between">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                Placement readiness
              </p>
              <p className="mt-1 text-sm text-slate-500">
                Weighted across attendance, assessments and interviews
              </p>
            </div>
            <Badge tone="brand">{titleCase(metrics?.rankBand || "unranked")}</Badge>
          </div>
          <div className="mt-5 flex items-center gap-6">
            <ReadinessRing value={metrics?.readinessScore} />
            <div className="flex-1 space-y-3">
              <Breakdown label="Attendance" value={metrics?.readiness?.attendance} />
              <Breakdown label="Assessments" value={metrics?.readiness?.assessment} />
              <Breakdown label="Interviews" value={metrics?.readiness?.interview} />
              <Breakdown label="Profile" value={metrics?.readiness?.profile} />
            </div>
          </div>
          <div className="mt-5 rounded-lg bg-slate-50 p-3 text-sm text-slate-600">
            <p className="font-semibold text-slate-800">
              {student?.placementStatus === "placed"
                ? `Placed at ${student.placedCompany} (${number(student.placedCtc, 1)} LPA)`
                : "Keep building your readiness"}
            </p>
            <p className="mt-1 text-xs">
              {student?.atRisk
                ? "You are below the batch attendance threshold. Talk to your trainer."
                : "Attendance and assessments update automatically after every session."}
            </p>
          </div>
        </Card>

        <div className="grid gap-4 sm:grid-cols-2 lg:col-span-2">
          <StatCard label="Attendance" value={pct(metrics?.attendancePct)} hint="Present + late + excused" icon="check" tone="green" />
          <StatCard label="Assessment average" value={pct(metrics?.assessmentAvg)} hint="Weighted across assessments" icon="reports" tone="blue" />
          <StatCard label="Interview average" value={pct(metrics?.interviewAvg)} hint="Four skill ratings, normalised" icon="students" tone="amber" />
          <StatCard label="Profile completeness" value={`${metrics?.profileScore ?? 0}/100`} hint="Skills, projects, resume, links" icon="user" tone="brand" />
        </div>
      </div>

      <div className="mt-5 grid gap-5 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader title="Progress trends" subtitle="Recent attendance, assessment and interview signals" />
          <div className="grid gap-6 p-5 sm:grid-cols-3">
            <Trend title="Attendance" points={metrics?.attendanceTrend} tone="brand" />
            <Trend title="Assessments" points={metrics?.scoreTrend} tone="blue" />
            <Trend
              title="Interviews"
              points={(metrics?.interviewTrend || []).map((point) => ({
                label: point.date,
                value: Number(point.average || 0) * 20,
              }))}
              tone="amber"
            />
          </div>
        </Card>

        <Card>
          <CardHeader
            title="Upcoming drives"
            subtitle="Eligibility is evaluated live"
            action={<Link to="/drives" className="text-xs font-semibold text-brand-700">View all</Link>}
          />
          <div className="divide-y divide-slate-100">
            {(drives.data?.items || []).length === 0 ? (
              <EmptyState title="No open drives" body="New drives appear here as soon as they are published." />
            ) : (
              (drives.data?.items || []).map((drive) => {
                const eligibility = drive.eligibilityResult;
                return (
                  <div key={drive.id} className="p-4">
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <p className="text-sm font-semibold text-slate-900">{drive.companyName}</p>
                        <p className="text-xs text-slate-500">
                          {drive.role} · {number(drive.ctc, 1)} LPA
                        </p>
                      </div>
                      {eligibility ? (
                        <Badge tone={eligibility.eligible ? "green" : "rose"}>
                          {eligibility.eligible ? "Eligible" : "Not eligible"}
                        </Badge>
                      ) : null}
                    </div>
                    <p className="mt-2 text-xs text-slate-500">
                      Apply by {formatDate(drive.deadline)}
                      {drive.application ? ` · ${titleCase(drive.application.status)}` : ""}
                    </p>
                    {eligibility && !eligibility.eligible && eligibility.reasons?.length ? (
                      <p className="mt-1 text-xs text-rose-600">{eligibility.reasons[0]}</p>
                    ) : null}
                  </div>
                );
              })
            )}
          </div>
        </Card>
      </div>
    </div>
  );
}

function AdminDashboard({ me }) {
  const placements = useAsync(() => api("/analytics/placements"), []);
  const atRisk = useAsync(() => api("/students", { query: { atRisk: true, limit: 5 } }), []);
  const drives = useAsync(() => api("/drives", { query: { limit: 5 } }), []);
  const metrics = placements.data;

  if (placements.loading) return <Spinner label="Building placement analytics…" />;

  return (
    <div>
      <PageHeader
        title={`Placement overview`}
        subtitle={`${me.superAdmin ? "All colleges" : `${me.collegeIds?.length || 0} college(s)`} · live aggregation`}
      >
        <Link to="/reports" className="btn-secondary">
          <Icon name="reports" className="h-4 w-4" />
          Export report
        </Link>
        <Link to="/drives" className="btn-primary">
          <Icon name="plus" className="h-4 w-4" />
          New drive
        </Link>
      </PageHeader>

      <ErrorBanner error={placements.error || atRisk.error || drives.error} />

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Students in scope" value={metrics?.students ?? 0} hint="Across visible colleges" icon="students" />
        <StatCard label="Placed" value={metrics?.placed ?? 0} hint={pct(metrics?.placementRate)} icon="check" tone="green" />
        <StatCard label="Average package" value={`${number(metrics?.averagePackage, 1)} LPA`} hint="Across placed students" icon="drives" tone="blue" />
        <StatCard label="Highest package" value={`${number(metrics?.highestPackage, 1)} LPA`} hint={`Median ${number(metrics?.medianPackage, 1)} LPA`} icon="reports" tone="amber" />
      </div>

      <div className="mt-5 grid gap-5 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader title="Placement funnel" subtitle="Eligible → applied → shortlisted → selected" />
          <div className="space-y-4 p-5">
            <Funnel label="Eligible students" value={metrics?.funnel?.eligible} total={metrics?.students} />
            <Funnel label="Applied" value={metrics?.funnel?.applied} total={metrics?.funnel?.eligible} />
            <Funnel label="Shortlisted / in process" value={metrics?.funnel?.shortlisted} total={metrics?.funnel?.applied} />
            <Funnel label="Selected" value={metrics?.funnel?.selected} total={metrics?.funnel?.shortlisted} tone="green" />
          </div>
          <div className="grid grid-cols-3 gap-3 border-t border-slate-100 p-5 text-center">
            <Conversion label="Applied / eligible" value={metrics?.funnel?.conversionRates?.appliedToEligible} />
            <Conversion label="Shortlisted / applied" value={metrics?.funnel?.conversionRates?.shortlistedToApplied} />
            <Conversion label="Selected / shortlisted" value={metrics?.funnel?.conversionRates?.selectedToShortlisted} />
          </div>
        </Card>

        <Card>
          <CardHeader title="At-risk students" subtitle="Attendance below batch threshold" action={<Link to="/students?atRisk=true" className="text-xs font-semibold text-brand-700">View</Link>} />
          <StudentList
            items={atRisk.data?.items}
            empty="No at-risk students in scope."
            showAttendance
          />
        </Card>
      </div>

      <div className="mt-5 grid gap-5 lg:grid-cols-2">
        <Card>
          <CardHeader title="Placements by branch" subtitle="Rate and volume" />
          <div className="divide-y divide-slate-100">
            {(metrics?.byBranch || []).length === 0 ? (
              <EmptyState title="No branch data" />
            ) : (
              metrics.byBranch.map((row) => (
                <div key={row.branch} className="flex items-center gap-4 px-5 py-3">
                  <span className="w-28 truncate text-sm font-semibold text-slate-800">{row.branch}</span>
                  <div className="flex-1">
                    <Progress value={row.placementRate} tone={row.placementRate >= 60 ? "green" : "brand"} />
                  </div>
                  <span className="w-24 text-right text-xs text-slate-500">
                    {row.placed}/{row.students} · {row.placementRate}%
                  </span>
                </div>
              ))
            )}
          </div>
        </Card>

        <Card>
          <CardHeader title="Recent drives" subtitle="Latest published opportunities" action={<Link to="/drives" className="text-xs font-semibold text-brand-700">Manage</Link>} />
          <div className="divide-y divide-slate-100">
            {(drives.data?.items || []).length === 0 ? (
              <EmptyState title="No drives yet" body="Create a drive to start the placement season." />
            ) : (
              (drives.data?.items || []).map((drive) => (
                <div key={drive.id} className="flex items-center gap-3 px-5 py-3">
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-semibold text-slate-900">{drive.companyName}</p>
                    <p className="truncate text-xs text-slate-500">
                      {drive.role} · {formatDate(drive.driveDate)}
                    </p>
                  </div>
                  <StatusBadge status={drive.status} />
                  <span className="text-xs font-semibold text-slate-600">
                    {drive.stats?.applied ?? 0} applied
                  </span>
                </div>
              ))
            )}
          </div>
        </Card>
      </div>
    </div>
  );
}

function TrainerDashboard({ me }) {
  const batches = useAsync(() => api("/batches", { query: { limit: 100 } }), []);
  const [selectedId, setSelectedId] = useState(null);
  const batchList = batches.data?.items || [];
  const activeId = selectedId || batchList[0]?.id;
  const analytics = useAsync(
    () => (activeId ? api(`/analytics/batch/${activeId}`) : Promise.resolve(null)),
    [activeId]
  );
  const metrics = analytics.data;

  if (batches.loading) return <Spinner label="Loading your batches…" />;

  return (
    <div>
      <PageHeader
        title="Trainer dashboard"
        subtitle={`${me.name} · ${batchList.length} assigned batch(es)`}
      >
        {batchList.length > 1 ? (
          <select
            className="input max-w-xs"
            value={activeId || ""}
            onChange={(event) => setSelectedId(event.target.value)}
            aria-label="Select batch"
          >
            {batchList.map((batch) => (
              <option key={batch.id} value={batch.id}>
                {batch.name}
              </option>
            ))}
          </select>
        ) : null}
        <Link to="/batches" className="btn-secondary">
          Manage batches
        </Link>
      </PageHeader>

      <ErrorBanner error={batches.error || analytics.error} />

      {!activeId ? (
        <Card>
          <EmptyState
            title="No batches assigned"
            body="Ask an administrator to assign you to a batch. Attendance, assessments and feedback appear here afterwards."
          />
        </Card>
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <StatCard label="Students" value={metrics?.students ?? 0} hint={metrics?.batchName} icon="students" />
            <StatCard label="Average attendance" value={pct(metrics?.averageAttendance)} icon="check" tone="green" />
            <StatCard label="Average assessment" value={pct(metrics?.averageAssessment)} icon="reports" tone="blue" />
            <StatCard label="Placement rate" value={pct(metrics?.placementRate)} hint={pct(metrics?.averageReadiness) + " readiness"} icon="drives" tone="amber" />
          </div>

          <div className="mt-5 grid gap-5 lg:grid-cols-2">
            <Card>
              <CardHeader title="Students needing support" subtitle="Lowest attendance first" action={<Link to={`/batches/${activeId}`} className="text-xs font-semibold text-brand-700">Open batch</Link>} />
              <StudentList items={metrics?.atRisk} empty="No at-risk students — nice work." showAttendance />
            </Card>
            <Card>
              <CardHeader title="Top readiness" subtitle="Highest weighted readiness scores" />
              <div className="divide-y divide-slate-100">
                {(metrics?.topStudents || []).length === 0 ? (
                  <EmptyState title="No students yet" />
                ) : (
                  metrics.topStudents.map((student, index) => (
                    <div key={student.studentId} className="flex items-center gap-3 px-5 py-3">
                      <span className="w-6 text-xs font-bold text-slate-400">#{index + 1}</span>
                      <Avatar name={student.name} size="sm" />
                      <Link to={`/students/${student.studentId}`} className="min-w-0 flex-1 truncate text-sm font-semibold text-slate-800 hover:text-brand-700">
                        {student.name}
                      </Link>
                      <span className="text-xs text-slate-500">{pct(student.assessmentAvg)}</span>
                      <Badge tone="brand">{Math.round(student.readinessScore)}</Badge>
                    </div>
                  ))
                )}
              </div>
            </Card>
          </div>

          <div className="mt-5 grid gap-5 lg:grid-cols-2">
            <Card>
              <CardHeader title="Attendance by session" subtitle="Share of students credited" />
              <div className="p-5">
                <MiniBars
                  data={(metrics?.attendanceHeatmap || []).map((row) => ({
                    label: row.date || row.topic || "Session",
                    value: row.percentage,
                  }))}
                />
              </div>
            </Card>
            <Card>
              <CardHeader title="Assessment distribution" subtitle="Number of score records per band" />
              <div className="p-5">
                <MiniBars data={metrics?.assessmentDistribution || []} valueKey="count" />
              </div>
            </Card>
          </div>
        </>
      )}
    </div>
  );
}

function Breakdown({ label, value }) {
  return (
    <div>
      <div className="mb-1 flex items-center justify-between text-xs">
        <span className="font-medium text-slate-600">{label}</span>
        <span className="font-semibold text-slate-800">{Math.round(Number(value) || 0)}</span>
      </div>
      <Progress value={value} />
    </div>
  );
}

function Trend({ title, points = [], tone }) {
  return (
    <div>
      <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">{title}</p>
      <MiniBars data={points || []} />
      <p className="mt-2 text-xs text-slate-400">
        {(points || []).length ? `${points.length} recent point(s)` : "No data recorded"}
      </p>
    </div>
  );
}

function Funnel({ label, value = 0, total = 0, tone = "brand" }) {
  const percent = total ? Math.round((Number(value) / Number(total)) * 100) : 0;
  return (
    <div>
      <div className="mb-1 flex items-center justify-between text-sm">
        <span className="font-medium text-slate-700">{label}</span>
        <span className="font-semibold text-slate-900">
          {value ?? 0} <span className="text-xs font-normal text-slate-500">({percent}%)</span>
        </span>
      </div>
      <Progress value={percent} tone={tone} />
    </div>
  );
}

function Conversion({ label, value }) {
  return (
    <div>
      <p className="text-lg font-bold text-slate-900">{pct(value, 0)}</p>
      <p className="text-[11px] text-slate-500">{label}</p>
    </div>
  );
}

function StudentList({ items = [], empty = "Nothing to show.", showAttendance = false }) {
  if (!items?.length) return <EmptyState title={empty} />;
  return (
    <div className="divide-y divide-slate-100">
      {items.map((student) => (
        <Link
          key={student.id || student.studentId}
          to={`/students/${student.id || student.studentId}`}
          className="flex items-center gap-3 px-5 py-3 hover:bg-slate-50"
        >
          <Avatar name={student.name} size="sm" />
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-semibold text-slate-800">{student.name}</p>
            <p className="truncate text-xs text-slate-500">
              {student.batchName || (showAttendance ? "Attendance watch" : "Student")}
            </p>
          </div>
          {showAttendance ? (
            <Badge tone={(student.attendancePct ?? 0) >= 75 ? "green" : "rose"}>
              {pct(student.attendancePct)}
            </Badge>
          ) : null}
        </Link>
      ))}
    </div>
  );
}
