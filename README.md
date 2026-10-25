# SPMS — Student Placement Management System

A placement-cell workspace for training institutes: student profiles, batches, attendance,
assessments, interview feedback, placement drives, eligibility, applications, offers,
notifications, audit trail and CSV/PDF reporting.

The API is FastAPI + Firebase (Auth, Firestore, Cloud Storage) and the web client is
React + Vite + Tailwind. It runs against the real Firebase project, or fully offline with an
in-memory store for a quick look.

- Product requirements: [`docs/PRD.md`](docs/PRD.md)
- Engineering conventions: [`AGENTS.md`](AGENTS.md)

---

## Quick start (Firebase-backed)

This is the normal mode: Firestore holds the data and Firebase Auth issues the ID tokens.
You need the service-account key for `placement-app-144e3` from the project owner.

```bash
# 1. install
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 2. point the checkout at the service-account key
python3 scripts/setup_local.py --service-account ~/Downloads/placement-app-144e3.json

# 3. verify Firestore + Auth, then start the API
.venv/bin/python scripts/setup_local.py --check
.venv/bin/uvicorn app.main:app --port 8080

# 4. web client (new terminal)
cd web
npm install
npm run dev          # http://localhost:5173
```

`setup_local.py` is the only setup step. It copies the key to `secrets/service-account.json`
(git-ignored, mode 600), writes `.env` (`USE_FIREBASE=true`, project id, key path, matching
storage bucket, cache warm-up), and creates `web/.env` from `web/.env.example`, which already
carries the project's public Firebase web config. Every value it writes is a default:
re-running it never overwrites a non-empty setting you changed. `--check` samples Firestore
and Firebase Auth and exits non-zero if the key, project or APIs are wrong.

Sign in on the **Email & password** tab with an account from the project (for example
`admin@spms.dev`); the owner shares the passwords. The **Development** tab only works in
demo mode, because it bypasses Firebase Auth.

`secrets/` is git-ignored. Never commit the service-account key, and rotate it if it has
been shared outside the team.

### If something fails

| Symptom | Cause and fix |
| --- | --- |
| `RuntimeError: GOOGLE_APPLICATION_CREDENTIALS points to …` | The key is not at `secrets/service-account.json`; re-run `setup_local.py --service-account …`. |
| `PermissionDenied` / `The caller does not have permission` | The key belongs to a different Firebase project, or the Firestore API is disabled for it. |
| `Token verification failed` after entering the password | The login reached Firebase but the API rejected the token; restart the API so it reloads `.env`. |
| Resume upload returns `503 storage_unavailable` | Cloud Storage is not provisioned on the free plan; every other feature works. |
| `uvicorn: command not found` | Use `.venv/bin/uvicorn` (or activate the venv first). |

---

## Quick start (demo mode, no Firebase)

Useful for a screenshots-only run or for CI. No credentials, data in memory, reset on
restart.

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env

SEED_DEMO=true .venv/bin/uvicorn app.main:app --reload --port 8080

cd web && npm install && npm run dev     # http://localhost:5173
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
  tests/             # 83 API tests, no production credentials required
  scripts/           # local Firebase setup, seed reference data, create a super admin
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
needs Firebase credentials. Current status: **83 passing**, ~84% statement coverage.

## Performance

Every Firestore call is a network round-trip, and on a slow path to Google's APIs a single
document read can take 0.4–2.5 s. The API therefore avoids round-trips instead of trying to
make them faster:

- **Read-through cache** in `FirestoreStore` (`FIRESTORE_CACHE_TTL_SECONDS`, default 30).
  Entries are fresh for the TTL; after that the stale entry is still served immediately while
  one background task refreshes it (stale-while-revalidate). Writes through the same process
  bump a per-collection generation, so a mutation is visible to the next read.
- **Bulk reads** (`counts_by`, `all_in`) replace the per-row counts/lookups that list screens
  used to issue. `colleges`, `companies`, `drives` and `applications` decorate a whole page with
  one or two queries.
- **Parallel reads** (`app/core/concurrency.py`) fan independent reads out on a small pool, so
  a dashboard pays the slowest read rather than the sum.
- **Startup warm** (`FIRESTORE_WARM_CACHE=true`) calls the same service `list` methods the
  screens call (colleges, companies, batches, users, students, applications, drives and the
  placements dashboard) with the page sizes the web client requests, on a background thread.
  The first screen after a restart does not wait for them.
- **In-flight GET dedupe** in the web client: identical concurrent GETs (React StrictMode runs
  effects twice) share one request.

Measure it with:

```bash
SPMS_API_KEY=<web-api-key> SPMS_EMAIL=admin@... SPMS_PASSWORD=... \
  .venv/bin/python scripts/bench_api.py
```

Expected shape: the first call to each endpoint is cold (network bound), repeats are single-digit
milliseconds. The cache is per process, so with several Cloud Run instances a read can be up to
one TTL stale on an instance that did not handle the write.

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
- `web/.env` (git-ignored, created by `setup_local.py` from `web/.env.example`) contains the
  web app's `VITE_FIREBASE_*` config, so the **Email & password** tab works after
  `npm run dev`.
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

The Vite client reads `VITE_FIREBASE_*` from `web/.env` (git-ignored; `setup_local.py`
creates it, and `web/.env.example` is the checked-in template with this project's public
config) and enables the **Email & password** tab. Without those values, only development
tokens work. The client calls `/api/v1`
through Vite's dev proxy; override the target with `VITE_PROXY_TARGET` (default
`http://localhost:8080`) or set `VITE_API_BASE_URL` for a production build.

---

## Deploy (optional)

Local, Firebase-backed runs are the supported setup. The repository can also be split into
a static React client and a Python API, but as of now no public API is running, so the
hosted client cannot sign in.

| Piece | Host | Cost | Notes |
| --- | --- | --- | --- |
| Client | Hugging Face static Space | free | `scripts/deploy_hf_web.py`; needs a reachable API URL |
| API | Render (Docker) | free | `render.yaml`, sleeps when idle |

### Client (Hugging Face static Space)

`scripts/deploy_hf_web.py` builds `web/` locally (so `web/.env`'s Firebase config is baked
in) and uploads `dist/` to a static Space. `VITE_API_BASE_URL` is inlined at build time —
re-run the script whenever the API URL changes.

```bash
python3 scripts/deploy_hf_web.py --space <user>/spms-web --api-base https://<api-host>/api/v1
```

The site is served from `https://<user>-<space>.static.hf.space`. Static Spaces have no
rewrite rules, so only `/` loads directly; in-app navigation works, but refreshing a deep
link returns HF's 404. Add that domain to **Firebase console → Authentication → Settings →
Authorized domains**.

### Client (Netlify, alternative)

`netlify.toml` builds `web/` (`npm ci && npm run build`) and publishes `web/dist` with an
SPA fallback to `index.html`. Connect the repo in the Netlify UI, then set
`VITE_API_BASE_URL` plus the `VITE_FIREBASE_*` variables from `web/.env.example` in
**Site configuration → Environment variables** before the first build.

### API (Render)

`render.yaml` defines a free Docker web service running the repo's `Dockerfile`:

1. Render dashboard → **New → Blueprint** → pick the `spms` repository.
2. Provide the service account. Render's **Secret Files** did not mount reliably for this
   service, so use environment variables: split the key JSON into two halves and set
   `GOOGLE_APPLICATION_CREDENTIALS_JSON_1` and `GOOGLE_APPLICATION_CREDENTIALS_JSON_2`
   (each ~1.2 KB; the app concatenates `_1`…`_9` in order before parsing). Do not paste the
   whole key into one variable: the dashboard truncates long values and startup fails with
   `Expecting property name enclosed in double quotes`.
   If you do upload it as a **Secret File** named `service-account.json`, Render mounts it at
   `/etc/secrets/service-account.json` and the blueprint's `GOOGLE_APPLICATION_CREDENTIALS`
   points there; the image runs as UID/GID 1000 so the file is readable, and projected mounts
   (k8s-style `..data` directories) are searched. A mounted file wins over inline values.
3. Set `CORS_ORIGINS` to the client origin, e.g.
   `https://<user>-spms-web.static.hf.space` (public value, editable in the blueprint).
4. `FIREBASE_PROJECT_ID`, `FIRESTORE_WARM_CACHE`, `WEB_CONCURRENCY=1` and the rest are set
   by the blueprint.

Free services sleep after 15 minutes idle, so the first request afterwards pays a cold
start; the startup cache warm-up then runs in the background. Health probe: `/health`.

### API (Cloud Run, alternative)

```bash
gcloud run deploy spms-api --source . --region asia-south1 --allow-unauthenticated
```

Grant the runtime service account Firestore access instead of shipping a key, and set
`USE_FIREBASE=true`, `CORS_ORIGINS`, `FIREBASE_PROJECT_ID`, the readiness/attendance
variables and `FIRESTORE_WARM_CACHE=true`.

### API (Hugging Face Space, requires PRO)

Docker Spaces on Hugging Face need a PRO subscription ($9/month); static Spaces are free.
With PRO, `scripts/deploy_hf.py` stages the backend and publishes it with the same
`Dockerfile`, uploading `secrets/service-account.json` as a write-only Space secret:

```bash
python3 scripts/deploy_hf.py --space <user>/spms-api --cors https://<site>
```

Uploaded resumes and offer letters are never public: the API returns short-lived signed
URLs (`SIGNED_URL_TTL_SECONDS`).

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
