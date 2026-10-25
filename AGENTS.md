# AGENTS.md — SPMS

Student Placement Management System. FastAPI + Firebase (Auth, Firestore, Storage).

## Stack

| Layer | Choice |
| --- | --- |
| API | Python 3.11+, FastAPI, Pydantic v2, Uvicorn |
| Auth | Firebase Authentication ID tokens + custom claims (`role`, `collegeIds`, `superAdmin`) |
| Database | Cloud Firestore via `firebase-admin` |
| Files | Firebase Cloud Storage (signed URLs only) |
| Web client | React 18 + Vite + Tailwind |
| Hosting | Hugging Face static Space or Netlify (React client), Render or Cloud Run (FastAPI Docker) |
| Tests | pytest, httpx, in-memory store, optional Firebase Emulator Suite |

## Folder structure

```
spms/
  app/
    main.py
    core/          # config, firebase init, security deps, errors, pagination, logging
    models/        # Pydantic v2 schemas (API + entities)
    routers/       # auth, users, colleges, batches, students, attendance,
                   # assessments, companies, drives, applications, feedback,
                   # analytics, notifications
    services/      # business logic (eligibility, readiness score, exports, ...)
    repositories/  # Firestore access layer (DocumentStore + repositories)
  tests/
  scripts/         # seed data, create super admin
  web/             # React + Vite + Tailwind client
  firebase.json, firestore.rules, firestore.indexes.json, storage.rules
  Dockerfile, requirements.txt, .env.example, AGENTS.md
```

## Coding rules

1. Type hints on every public function. Pydantic v2 only (`model_config`, `field_validator`).
2. Layering is strict: **routers → services → repositories**. No Firestore or `google.cloud` imports in `routers/` or `services/`.
3. Every endpoint declares an auth dependency. Use `require_roles(...)` (or `get_current_user` for self-service routes). There are no anonymous endpoints except `/health` and `/docs`.
4. Every data read/write is college-scoped: call `scope.assert_college(user, college_id)` (admins/trainers limited to `collegeIds`; students to their own college).
5. Errors use `AppError(code, message, status)` subclasses; the handler renders `{code, message, details}`.
6. Firestore documents use camelCase keys. Pydantic models use snake_case + `to_camel` alias generator, so `model_dump(by_alias=True)` is the Firestore payload.
7. All list endpoints paginate: `limit` (default 20, max 100) and opaque `cursor`. No unbounded scans.
8. Denormalize `studentName`, `batchName`, `collegeId` onto applications/scores/attendance; update precomputed aggregates on the `students` document in the same service call.
9. Audit every mutation of attendance, scores, drive outcomes, roles, and student imports via `AuditService`.
10. Tests must not need production credentials. Use `app.dependency_overrides[get_store]` + `app.dependency_overrides[get_current_user]`.

## Roles and scoping

- `admin`: full access to colleges in `collegeIds`. `superAdmin: true` (or `collegeIds` containing `*`) means all colleges.
- `trainer`: read/write only batches they teach, within their colleges.
- `student`: only their own profile, attendance, scores, feedback, applications.

## Commands

```bash
# install
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt

# run API (memory store, no Firebase needed)
.venv/bin/uvicorn app.main:app --reload --port 8080

# tests + coverage
.venv/bin/pytest -q --cov=app --cov-report=term-missing

# Firebase emulators (Auth 9099, Firestore 8081, Storage 9199, UI 4000)
firebase emulators:start --only auth,firestore,storage

# point the app at emulators
export FIREBASE_AUTH_EMULATOR_HOST=127.0.0.1:9099
export FIRESTORE_EMULATOR_HOST=127.0.0.1:8081
export FIREBASE_STORAGE_EMULATOR_HOST=127.0.0.1:9199
export USE_FIREBASE=true

# seed data
.venv/bin/python scripts/seed.py

# create super admin
.venv/bin/python scripts/create_super_admin.py --email admin@spms.dev --password 'ChangeMe123!'

# frontend
cd web && npm install && npm run dev
```

## Phase checklist

- [x] Phase 0: repo, Firebase wiring, auth dependency, RBAC, CI-ready tests
- [x] Phase 1: users, colleges, batches, student profiles, CSV import
- [x] Phase 2: attendance and assessments
- [x] Phase 3: companies, drives, eligibility engine, applications, outcomes
- [x] Phase 4: interview feedback, notifications, audit log
- [x] Phase 5: analytics, readiness score, CSV/PDF exports
- [x] Phase 6: hardening, Firestore/Storage rules, Docker, Cloud Run config

## Environment

Copy `.env.example` → `.env`. `USE_FIREBASE=false` (default) runs an in-memory store so the API
boots without credentials; production/emulator runs use `USE_FIREBASE=true`.

## Known deviations

- MCQ quiz mode (FR-22) is deliberately out of scope for v1.1 (`type=mock_test` scoring works).
- FCM push is not implemented; in-app notifications + email queue documents are.
- `analytics_snapshots` are written by `POST /analytics/{scope}/{id}/snapshot` and read by dashboards;
  dashboards fall back to live aggregation when no snapshot exists.
