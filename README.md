# SPMS — Student Placement Management System

A placement-cell workspace for training institutes: student profiles, batches, attendance,
assessments, interview feedback, placement drives, eligibility, applications, offers,
notifications, audit trail and CSV/PDF reporting.

The API is FastAPI + Firebase (Auth, Firestore, Cloud Storage) and the web client is
React + Vite + Tailwind. **The whole stack runs locally with no Firebase credentials** using
an in-memory document store and development tokens.

- Product requirements: [`docs/PRD.md`](docs/PRD.md)
- Engineering conventions: [`AGENTS.md`](AGENTS.md)

---

## Quick start (demo mode, no Firebase)

```bash
# 1. Backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env

SEED_DEMO=true .venv/bin/uvicorn app.main:app --reload --port 8080

# 2. Web client (new terminal)
cd web
npm install
npm run dev          # http://localhost:5173
```

Open <http://localhost:5173> and sign in with a demo account. The **Development**
tab sends `Authorization: Bearer dev:<uid>`.

| Account | Role | What to try |
| --- | --- | --- |
| `demo-admin` | Super admin | Dashboard, drives, applications, reports, audit log |
| `demo-trainer` | Trainer | Batch attendance, assessments, interview feedback |
| `demo-student-1` | Student (Aarav) | Readiness ≈ 87, open Innovate Labs drive |
| `demo-student-2` | Student (Diya) | At-risk attendance (50%), lower readiness |

Demo data is seeded at startup only when `USE_FIREBASE=false` **and** `SEED_DEMO=true`.
It lives in memory, so restarting the API resets it.

Useful URLs:

- Swagger UI: <http://localhost:8080/docs>
- ReDoc: <http://localhost:8080/redoc>
- Health: <http://localhost:8080/health>

### What the web client covers

- **Admin:** placement dashboard, student search + CSV import, batches (sessions,
  attendance, assessments, student assignment), drives, applications and outcomes,
  colleges, companies, people (trainers/admins/students), reports, audit log,
  notifications.
- **Trainer:** dashboard, students, batches (attendance and scores), drives,
  applications, notifications, interview feedback on student profiles.
- **Student:** dashboard, own profile and resume, drives with eligibility reasons,
  applications, notifications, feedback without internal notes.

---

## Stack

| Layer | Choice |
| --- | --- |
| API | Python 3.11+, FastAPI, Pydantic v2, Uvicorn |
| Auth | Firebase Authentication ID tokens + custom claims (`role`, `collegeIds`, `superAdmin`) |
| Database | Cloud Firestore via `firebase-admin`; in-memory store for local dev/tests |
| Files | Firebase Cloud Storage (signed URLs only) |
| Web client | React 18, Vite, Tailwind CSS, React Router |
| Hosting | Cloud Run (API Docker image), Firebase Hosting (web client) |
| Tests | pytest + httpx, in-memory store, optional Firebase Emulator Suite |

## Layout

```
spms/
  app/
    main.py          # app wiring, middleware, lifespan demo seeding
    core/            # config, firebase, security, scoping, errors, pagination, demo data
    models/          # Pydantic v2 schemas
    routers/         # HTTP endpoints (auth → services)
    services/        # business logic (eligibility, readiness, exports, audit, …)
    repositories/    # DocumentStore implementations + repositories
  tests/             # 62 API tests, no production credentials required
  scripts/           # seed reference data, create a Firebase super admin
  web/               # React + Vite client
  docs/PRD.md
  firebase.json, firestore.rules, firestore.indexes.json, storage.rules
  Dockerfile, requirements.txt, .env.example
```

Layering is strict: **routers → services → repositories**. Only repositories talk to
Firestore. Every endpoint declares an auth dependency, and every data access is
college-scoped (`collegeIds` claim, `superAdmin` bypasses).

---

## Tests

```bash
.venv/bin/pytest -q
.venv/bin/pytest -q --cov=app --cov-report=term-missing
```

The suite uses `app.dependency_overrides` for the store and `dev:` tokens, so it never
needs Firebase credentials. Current status: **62 passing**, ~84% statement coverage.

## API surface

All endpoints live under `/api/v1`. Lists use `limit` (default 20, max 100) and an opaque
`cursor`; errors return `{code, message, details}`.

| Area | Endpoints |
| --- | --- |
| Auth / users | `/auth/me`, `/users`, `/users/{id}` |
| Catalog | `/colleges`, `/batches`, `/companies` |
| Students | `/students`, `/students/{id}`, resume upload + signed URL, CSV import |
| Attendance | `/batches/{id}/sessions`, `/sessions/{id}/attendance`, corrections, summaries |
| Assessments | `/assessments`, scores, CSV import, per-assessment analytics |
| Drives | `/drives`, `/drives/{id}`, eligible students, apply |
| Applications | `/applications`, round results, outcomes, offer letters |
| Feedback | `/feedback`, `/students/{id}/feedback` (students never see internal notes) |
| Analytics | `/analytics/student/{id}`, `/analytics/batch/{id}`, `/analytics/placements` |
| Notifications / audit | `/notifications`, `/audit-logs` |
| Reports | `/reports/export?report=…&format=csv\|pdf` |

### Readiness score

`attendance × 0.20 + assessment × 0.40 + interview × 0.30 + profile × 0.10`

Weights come from environment variables. When a student has no interview feedback yet,
the remaining weights are re-normalized instead of scoring interviews as zero. The score
is refreshed after attendance, score, feedback and profile mutations.

### Eligibility

A drive can require minimum CGPA, attendance, assessment average, branches, batches and
colleges. Students see an explicit `reasons` list when blocked. Placed students are
ineligible for other drives unless the drive allows dream offers and the student's
`placementLocked` flag is cleared by an admin.

---

## Firebase setup

### Emulators

```bash
npm install                       # installs firebase-tools locally
npx firebase emulators:start --only auth,firestore,storage

export FIREBASE_AUTH_EMULATOR_HOST=127.0.0.1:9099
export FIRESTORE_EMULATOR_HOST=127.0.0.1:8081
export FIREBASE_STORAGE_EMULATOR_HOST=127.0.0.1:9199
export USE_FIREBASE=true
.venv/bin/uvicorn app.main:app --reload --port 8080
```

### Real project (placement-app-144e3)

This checkout is already wired to the `placement-app-144e3` Firebase project:

- `.firebaserc` sets it as the default project for the Firebase CLI.
- `web/.env` (git-ignored) contains the web app's `VITE_FIREBASE_*` config, so the
  **Email & password** tab works after `npm run dev`.
- Auth (email/password) and the Firestore `(default)` database are enabled.
- The web API key is a public client identifier, not a server secret. Never commit a
  service account key.

The API still needs server credentials:

1. Firebase console → **Project settings → Service accounts → Generate new private key**.
   Save the JSON as `secrets/service-account.json` (git-ignored).
2. Enable Cloud Storage in the console if it is not already active. Storage requires the
   Blaze (pay-as-you-go) plan; a project without a billing account cannot create a bucket.
3. In `.env`, set `USE_FIREBASE=true` and keep
   `FIREBASE_PROJECT_ID=placement-app-144e3` and
   `FIREBASE_STORAGE_BUCKET=placement-app-144e3.firebasestorage.app`.
4. Deploy rules and indexes **before seeding**. Composite indexes are created
   asynchronously; wait for them to reach `READY` in the console before the first seed:

```bash
npx firebase deploy --only firestore:rules,firestore:indexes
```

5. Seed reference/demo data and create the first admin:

```bash
.venv/bin/python scripts/seed.py
.venv/bin/python scripts/create_super_admin.py \
  --email admin@yourcollege.edu --password 'ChangeMe123!'
```

6. After the Cloud Storage bucket exists, deploy Storage rules: `npx firebase deploy --only storage`.

### Web client auth

The Vite client reads `VITE_FIREBASE_*` from `web/.env` (git-ignored; already populated for this
project) and enables the **Email & password** tab. Without those values, only development tokens
work. Use `web/.env.example` as the template on a fresh machine. The client calls `/api/v1`
through Vite's dev proxy; override the target with `VITE_PROXY_TARGET` (default
`http://localhost:8080`) or set `VITE_API_BASE_URL` for a production build.

---

## Deploy

**API (Cloud Run):**

```bash
gcloud run deploy spms-api --source . --region asia-south1 --allow-unauthenticated
```

Mount the service account via Secret Manager or a runtime service account, and set
`USE_FIREBASE=true`, `CORS_ORIGINS` and the readiness/attendance variables.

**Web (Firebase Hosting):**

```bash
cd web && VITE_API_BASE_URL=https://spms-api-…run.app/api/v1 npm run build
cd .. && npx firebase deploy --only hosting
```

`firebase.json` serves `web/dist` with SPA rewrites. Uploaded resumes and offer letters
are never public: the API returns short-lived signed URLs (`SIGNED_URL_TTL_SECONDS`).

---

## Conventions and limits

- Firestore documents use camelCase; Pydantic models use snake_case plus a `to_camel`
  alias generator, so `model_dump(by_alias=True)` is the Firestore payload.
- Attendance is credited for `present`, `late` and `excused`.
- Mutations of attendance, scores, drive outcomes, roles, imports and feedback are audited.
- Out of scope for v1.1: MCQ quiz engine, FCM push (in-app notifications and an email
  queue document are implemented), recruiter self-service portal, payments, native apps.
- `placement-app-144e3` has no billing account, so Cloud Storage cannot be provisioned.
  Resume and offer-letter uploads return `503 storage_unavailable` until the project is
  upgraded to Blaze and `placement-app-144e3.firebasestorage.app` exists. Auth, Firestore,
  dashboards, reports and notifications work on the free plan.
