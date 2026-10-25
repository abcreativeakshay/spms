# SPMS — Student Placement Management System

**Product Requirements Document (v1.0)**

| | |
| --- | --- |
| Status | Implemented (v1.0) |
| Owners | Placement Cell (product), Engineering (delivery) |
| Backend | FastAPI + Firebase Admin (Auth, Firestore, Storage) |
| Web client | React 18 + Vite + Tailwind CSS |
| Hosting | Cloud Run (API), Firebase Hosting (web) |

---

## 1. Problem statement

Training institutes and college placement cells track student readiness across
attendance, assessments and interviews, then match students to company drives.
Most teams do this in spreadsheets: eligibility is error-prone, placement stats
are stale, and students do not know why they are ineligible for a drive.

SPMS is a multi-tenant system that:

1. keeps one authoritative student profile per learner,
2. computes attendance, assessment, interview and readiness metrics continuously,
3. runs drive eligibility and application pipeline deterministically,
4. gives students, trainers and administrators role-appropriate dashboards, and
5. produces auditable exports for accreditation and management reporting.

## 2. Goals and success metrics

| Goal | Success metric |
| --- | --- |
| Single source of truth | 100% of active students have a profile, batch and college |
| Early intervention | At-risk students (attendance below batch threshold) flagged within one session |
| Transparent eligibility | Every drive displays eligibility and the exact blocking reasons |
| Faster placement reporting | College/placement reports export in under 5 seconds for 20k students |
| Data isolation | No cross-college read or write succeeds without `superAdmin` |
| Auditability | Attendance, score, outcome, role and import mutations leave an audit entry |

Non-goals for v1.0: native mobile apps, recruiter self-service portal, payments,
online proctoring, FCM push, and a full MCQ quiz engine.

## 3. Personas and roles

| Persona | Role | Scope |
| --- | --- | --- |
| Placement administrator | `admin` | Colleges in `collegeIds`; full CRUD, drives, outcomes, analytics, exports, users |
| Super administrator | `admin` + `superAdmin: true` | All colleges; creates colleges and other admins |
| Trainer | `trainer` | Batches they are assigned to, within their colleges; attendance, scores, feedback |
| Student | `student` | Own profile, attendance, scores, feedback, applications, notifications |

### Authorisation rules

- Every endpoint except `/health` and `/docs` requires a Firebase ID token
  (`Authorization: Bearer <token>`). In development only, `dev:<uid>` tokens are
  accepted when `USE_FIREBASE=false` or `ALLOW_DEV_TOKENS=true`.
- Role and college claims come from verified token custom claims, falling back to
  the `users` document.
- Admins/trainers are limited to their `collegeIds`; `superAdmin` (or `"*"` in
  `collegeIds`) bypasses college scoping.
- Trainers additionally need to be assigned to the batch (`trainerIds`).
- Students can only read and mutate their own records.
- Disabled accounts (`active=false`) are rejected on every request.

## 4. Functional requirements

### 4.1 Identity and access (FR-1 – FR-6)

- **FR-1** Sign in with Firebase Authentication; the API exposes `GET /auth/me`
  with role, college scope, super-admin flag and profile.
- **FR-2** Role-based access control with three roles (`admin`, `trainer`,
  `student`) enforced by dependency injection on every route.
- **FR-3** Token revocation (`POST /auth/logout-all`) invalidates refresh tokens.
- **FR-4** Admins can create, update, list, disable and re-enable users. Role
  changes are audited; student accounts cannot be converted to/from other roles.
- **FR-5** Users can be onboarded in bulk from CSV (`POST /users/bulk`) with
  per-row errors, duplicate detection and optional password-setup links.
- **FR-6** All reads/writes are college-scoped. Cross-college access returns
  `403 college_scope_violation`.

### 4.2 Colleges and batches (FR-7 – FR-9)

- **FR-7** College CRUD with deactivation (soft delete). Only super admins can
  create colleges. Renaming a college propagates `collegeName` to batches and
  students. List supports `q`, `active`, pagination.
- **FR-8** Batch CRUD with course, college, trainer assignment, start/end dates
  and attendance threshold. Trainers must belong to the batch's college; end date
  cannot precede start date.
- **FR-9** Students can be moved between batches (`POST /batches/{id}/students`,
  `move=true`) with immutable movement history (`batchAssignments`). Batch
  renaming propagates `batchName`; counts and at-risk flags are recomputed.

### 4.3 Student profiles (FR-10 – FR-14)

- **FR-10** Student profile contains identity, academics (roll no, degree,
  branch, graduation year, CGPA), skills, projects, certifications, links and
  resume path, plus denormalized college/batch names.
- **FR-11** Search and filter by college, batch, branch, placement status,
  readiness, attendance and skill with cursor pagination.
- **FR-12** Profile completeness score (0–100) with weights for identity,
  academics, skills, projects, certifications, links and resume.
- **FR-13** Resume upload to Cloud Storage; downloads are short-lived signed URLs
  (emulator mode returns a stable media URL).
- **FR-14** CSV import of students with per-row validation, duplicate detection
  and an audit entry. Students can read/update their own editable fields but not
  placement or aggregate fields.

### 4.4 Attendance (FR-15 – FR-18)

- **FR-15** Trainers create sessions (date, topic, duration) for their batches.
- **FR-16** Bulk attendance marking with `present`, `absent`, `late`, `excused`.
  Writes are idempotent on `{sessionId}_{studentId}`.
- **FR-17** Corrections are allowed within a configurable window
  (`ATTENDANCE_CORRECTION_WINDOW_DAYS`, default 7) and require a reason; every
  correction is audited.
- **FR-18** Student attendance summary (counts, percentage, threshold, history)
  and batch summary with heatmap, average and at-risk count. Present + late +
  excused count as credited attendance.

### 4.5 Assessments (FR-19 – FR-21)

- **FR-19** Assessments support `quiz`, `assignment`, `mock_test`,
  `mock_interview` and `aptitude`, with date, max marks and weightage.
- **FR-20** Scores are recorded individually or imported from CSV; the write is
  idempotent on `{assessmentId}_{studentId}` and validates `0 <= marks <= maxMarks`.
- **FR-21** Assessment analytics provide class average, distribution, toppers and
  per-student rank bands (`top_10_percent`, `top_25_percent`, `top_50_percent`,
  `bottom_50_percent`).

> **FR-22 (deferred)** Full MCQ quiz authoring, timed attempts and auto-grading
> are out of scope for v1.0. `type=mock_test` scoring is supported.

### 4.6 Companies, drives and applications (FR-23 – FR-28)

- **FR-23** Company catalogue CRUD with soft delete, search and drive counts.
  Company renaming propagates `companyName` to drives.
- **FR-24** Drives define company, role, CTC, location, date, deadline, rounds,
  eligible colleges and eligibility criteria (minimum CGPA, attendance,
  assessment average, batches, branches).
- **FR-25** Eligibility is evaluated on read. The API returns `eligible` plus
  human-readable `reasons` for each blocking criterion.
- **FR-26** Students apply once per drive (deterministic `{driveId}_{studentId}`
  document). Applications close at the deadline or when the drive is not open.
- **FR-27** Staff record round results (`shortlisted`, `cleared`, `rejected`,
  `absent`); clearing a round moves the application to `in_process`.
- **FR-28** Outcomes are `selected`, `rejected` or `withdrawn`. Selection writes
  `placedCompany`, `placedCtc` and `placementStatus=placed` on the student and
  locks further placements. The dream-offer policy allows a placed student to
  apply only when the drive has `allowDreamOffer=true` **and** the admin has
  cleared `placementLocked`. Withdrawing reverts the student to `unplaced`.
  Offer letters upload to Storage and are readable by the owning student.

### 4.7 Interview feedback (FR-29 – FR-31)

- **FR-29** Trainers record structured feedback: interview type, optional drive,
  date, four 1–5 ratings (technical, communication, problem solving, attitude),
  strengths, improvements, recommendation and internal notes.
- **FR-30** Students can read their own feedback, but `internalNotes` is removed
  before the response leaves the backend. Only staff see it.
- **FR-31** Feedback updates the student's interview average and readiness score
  and notifies the student.

### 4.8 Analytics and readiness (FR-32 – FR-35)

- **FR-32** Student dashboard: attendance/assessment/interview trends, profile
  score, readiness breakdown, placement status and rank band.
- **FR-33** Batch dashboard: student count, averages, placement rate, at-risk
  list, top students, attendance heatmap and assessment distribution.
- **FR-34** College dashboard: placement rate, average/highest package, readiness,
  and breakdowns by batch, branch and company.
- **FR-35** Placement dashboard: funnel (eligible → applied → shortlisted →
  selected), conversion rates, packages (average/highest/median), time to
  placement and breakdowns. Readiness is a weighted 0–100 score:
  attendance 20%, assessment 40%, interview 30%, profile 10%. When no interview
  feedback exists the interview weight is removed and the rest re-normalized.
- **FR-35a** Dashboards can be snapshotted (`POST /analytics/{scope}/{id}/snapshot`)
  and later read with `?snapshot=true`; live aggregation is the fallback.

### 4.9 Reporting (FR-36)

- **FR-36** Admins export five reports as CSV or PDF: `placements`, `students`,
  `applications`, `attendance`, `drives`. Exports honour college/batch filters
  and are always scoped to the caller's colleges. PDF summaries include headline
  placement metrics. Empty results return a valid file with a "No data" row.

### 4.10 Notifications, email and audit (FR-37 – FR-39)

- **FR-37** In-app notifications for drive, deadline, application, attendance,
  feedback and system events. Users list (optionally unread only), mark one or
  all as read, and cannot touch another user's inbox.
- **FR-38** Email delivery is queued to the `mail` collection consumed by the
  Firebase "Trigger Email" extension. FCM push is deferred.
- **FR-39** Every mutation of attendance, scores, drives/outcomes, feedback,
  roles and imports writes an audit entry with actor, action, entity, before/
  after, request id, timestamp and inferred college. Audit logs are readable by
  admins only and scoped to their colleges.

## 5. API conventions

- Base path `/api/v1`; OpenAPI at `/docs` and `/redoc`.
- Errors: `{"code": "...", "message": "...", "details": {...}}` with a stable
  snake_case `code`.
- Lists: `limit` (default 20, max 100) + opaque `cursor`; response
  `{items, nextCursor}`.
- Dates are ISO `YYYY-MM-DD`; timestamps are UTC ISO-8601.
- Request/response JSON is camelCase; Firestore documents are camelCase.
- Idempotency keys: attendance `{sessionId}_{studentId}`, scores
  `{assessmentId}_{studentId}`, applications `{driveId}_{studentId}`.
- See [API reference](#10-api-surface) and `/docs` for the full schema.

## 6. Data model (Firestore collections)

| Collection | Purpose | Key fields |
| --- | --- | --- |
| `users` | Accounts and claims mirror | `uid`, `role`, `collegeIds`, `superAdmin`, `active` |
| `colleges` | Tenant | `name`, `city`, `active` |
| `batches` | Cohorts | `collegeId`, `trainerIds`, `startDate`, `endDate`, `minAttendancePct` |
| `students` | Profiles + denormalized metrics | `uid`, `collegeId`, `batchId`, `profileScore`, `readinessScore`, `placementStatus` |
| `sessions` | Attendance sessions | `batchId`, `date`, `topic` |
| `attendance` | One row per student per session | `sessionId`, `studentId`, `status` |
| `assessments` | Assessment definition | `batchId`, `type`, `maxMarks`, `weightage` |
| `scores` | One row per student per assessment | `assessmentId`, `studentId`, `marks` |
| `companies` | Recruiter catalogue | `name`, `industry`, `active` |
| `drives` | Placement drives | `companyId`, `eligibility`, `rounds`, `status` |
| `applications` | Student ↔ drive | `studentId`, `driveId`, `roundResults`, `offer`, `status` |
| `feedback` | Interview feedback | `studentId`, `ratings`, `recommendation`, `internalNotes` |
| `notifications` | In-app inbox | `userId`, `type`, `read` |
| `audit` | Immutable trail | `actorId`, `action`, `entity`, `collegeId` |
| `analytics_snapshots` | Cached dashboards | `scope`, `scopeId`, `metrics`, `computedAt` |
| `batchAssignments` | Movement history | `studentId`, `fromBatchId`, `toBatchId`, `movedBy` |
| `mail` | Email queue | `to`, `message` |

Denormalized aggregates on `students` (`attendancePct`, `assessmentAvg`,
`interviewAvg`, `profileScore`, `readinessScore`, `atRisk`) are refreshed in the
same service call that changes the underlying data.

## 7. Non-functional requirements

| Area | Requirement |
| --- | --- |
| Performance | List endpoints never scan unbounded collections; dashboards target < 2s for 2k students; exports handle 20k students |
| Security | Firebase ID tokens verified with revocation check; least-privilege Firestore/Storage rules; signed URLs for files; no secrets in source |
| Privacy | Students never receive internal notes or other students' data; PII exports are admin-only |
| Reliability | Idempotent writes for attendance, scores and applications; deterministic cursor pagination |
| Observability | Structured JSON logs with request id, method, path, status and duration; audit trail for mutations |
| Portability | Runs without credentials via `USE_FIREBASE=false`; emulator suite supported |
| Accessibility | Web client uses semantic landmarks, labelled form controls and visible focus states |
| Browser support | Current Chrome, Edge, Firefox and Safari |

## 8. Delivery phases

| Phase | Scope | Status |
| --- | --- | --- |
| 0 | Repo, config, Firebase wiring, auth/RBAC, scoping, tests, CI-ready | Done |
| 1 | Users, colleges, batches, student profiles, resume, CSV import | Done |
| 2 | Attendance sessions/corrections/summaries, assessments and scores | Done |
| 3 | Companies, drives, eligibility, applications, rounds, outcomes | Done |
| 4 | Interview feedback, notifications, email queue, audit log | Done |
| 5 | Analytics, readiness score, snapshots, CSV/PDF exports | Done |
| 6 | Hardening, Firestore/Storage rules, indexes, Docker, Cloud Run, web client | Done |

## 9. Acceptance criteria (v1.0)

1. A super admin can create a college, batch, trainer and student, and the
   student can sign in and see only their own data.
2. A trainer can create a session, mark attendance, record an assessment score
   and submit interview feedback; all mutations appear in the audit log.
3. A student sees updated attendance, assessment average, readiness and feedback
   (without internal notes) on their dashboard.
4. An admin can publish a drive with eligibility criteria; eligible students can
   apply once, ineligible students see explicit reasons, and staff can advance
   rounds and record an outcome.
5. Selecting a candidate marks them placed, locks further offers and updates the
   college/placement dashboards; the dream-offer override is auditable.
6. An admin can export placements and student reports as CSV and PDF, scoped to
   their colleges.
7. `pytest --cov=app` passes with at least 70% coverage (currently 84%), and the
   API boots with `USE_FIREBASE=false` and reaches `/health`.
8. Firestore and Storage rules deny cross-college and unauthenticated access.

## 10. API surface

| Area | Endpoints |
| --- | --- |
| Auth | `GET /auth/me`, `POST /auth/logout-all` |
| Users | `GET/POST /users`, `GET/PATCH /users/{uid}`, `POST /users/{uid}/disable`, `POST /users/{uid}/enable`, `POST /users/bulk` |
| Colleges | `GET/POST /colleges`, `GET/PATCH/DELETE /colleges/{id}` |
| Batches | `GET/POST /batches`, `GET/PATCH/DELETE /batches/{id}`, `GET/POST /batches/{id}/students` |
| Students | `GET/POST /students`, `GET/PATCH /students/{id}`, resume upload/url, `POST /students/import` |
| Attendance | sessions, bulk marking, corrections, student history, batch summary |
| Assessments | CRUD, score entry/import, score listing, analytics |
| Companies | `GET/POST /companies`, `GET/PATCH/DELETE /companies/{id}` |
| Drives | CRUD, `GET /drives/{id}/eligible-students`, `POST /drives/{id}/apply` |
| Applications | list/get, round result, outcome, offer letter upload/url |
| Feedback | `POST /feedback`, `GET /students/{id}/feedback` |
| Analytics | student/batch/college/placements, snapshot create and cached read |
| Reports | `GET /reports/export?report=&format=csv|pdf` |
| Notifications | list, mark one/all read; `GET /audit-logs` |
| Health | `GET /health` |

## 11. Open questions and future work

- Recruiter self-service portal and interview scheduling.
- FCM push and WhatsApp notifications.
- Full quiz engine with timed attempts and proctoring.
- Placement policy configuration per college (multiple-offer rules).
- Data retention and PII deletion workflow.
- Native mobile clients.
