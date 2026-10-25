#!/usr/bin/env python
"""Seed SPMS reference and demo data.

Reference data (always): one college. ``--demo`` additionally creates a trainer,
students, sessions, an assessment, a company and an open drive.

Examples
--------
    # reference data only, against the Firestore emulator / production
    FIREBASE_AUTH_EMULATOR_HOST=127.0.0.1:9099 \
    FIRESTORE_EMULATOR_HOST=127.0.0.1:8081 \
    USE_FIREBASE=true .venv/bin/python scripts/seed.py

    # full demo dataset with a generated account password
    USE_FIREBASE=true .venv/bin/python scripts/seed.py --demo

The script is idempotent: existing documents are left untouched. Account
passwords are never stored in the repository; pass ``--password`` or set
``SEED_PASSWORD`` to control them, otherwise a random one is generated and
printed once.
"""

from __future__ import annotations

import argparse
import os
import secrets
import sys
from datetime import date, timedelta

from app.core.security import Principal
from app.models.enums import Role
from app.models.user import UserCreate
from app.repositories import Repos
from app.repositories.store import MemoryStore, get_store
from app.services.metrics import MetricsService, utcnow
from app.services.users import UsersService


def _heading(text: str) -> None:
    print(f"\n== {text} ==")


def _ensure_college(repos: Repos) -> dict:
    existing = repos.colleges.find_one(name="Demo Institute of Technology")
    if existing:
        return existing
    now = utcnow()
    return repos.colleges.create(
        {
            "name": "Demo Institute of Technology",
            "city": "Pune",
            "contactPerson": "Placement Cell",
            "contactEmail": "placements@demo.spms.test",
            "active": True,
            "createdAt": now,
            "updatedAt": now,
            "createdBy": "seed-script",
        }
    )


def _ensure_batch(repos: Repos, college: dict) -> dict:
    existing = next(
        (b for b in repos.batches.for_college(college["id"]) if b.get("name") == "Batch A"),
        None,
    )
    if existing:
        return existing
    today = date.today()
    return repos.batches.create(
        {
            "name": "Batch A",
            "course": "Full Stack Engineering",
            "collegeId": college["id"],
            "collegeName": college["name"],
            "trainerIds": [],
            "trainerNames": [],
            "startDate": (today - timedelta(days=45)).isoformat(),
            "endDate": (today + timedelta(days=135)).isoformat(),
            "minAttendancePct": 75.0,
            "status": "active",
            "studentCount": 0,
            "createdAt": utcnow(),
            "updatedAt": utcnow(),
            "createdBy": "seed-script",
        }
    )


def _ensure_account(
    users: UsersService,
    repos: Repos,
    actor: Principal,
    *,
    email: str,
    name: str,
    role: Role,
    college_id: str,
    password: str,
    student_profile: bool = False,
    **student_fields,
) -> tuple[dict, bool]:
    existing = repos.users.by_email(email)
    if existing:
        return existing, False

    payload: dict = {
        "name": name,
        "email": email,
        "role": role,
        "college_ids": [college_id],
        "password": password,
        "send_setup_email": False,
    }
    if student_profile:
        payload["college_id"] = college_id
        payload.update(student_fields)
    user, _ = users.create(actor, UserCreate(**payload))
    return repos.users.require(user["id"], "User"), True


def _seed_activity(repos: Repos, batch: dict, students: list[dict]) -> None:
    """Two sessions, two attendance marks and one assessment per student."""
    today = date.today()
    sessions = [
        ("demo-session-1", today - timedelta(days=2), "Python fundamentals"),
        ("demo-session-2", today - timedelta(days=1), "SQL joins"),
    ]
    for session_id, session_date, topic in sessions:
        repos.sessions.set(
            {
                "batchId": batch["id"],
                "date": session_date.isoformat(),
                "topic": topic,
                "trainerId": "demo-trainer",
                "trainerName": "Demo Trainer",
                "durationMinutes": 90,
                "marked": True,
                "presentCount": len(students),
                "totalCount": len(students),
                "createdAt": utcnow(),
            },
            doc_id=session_id,
        )

    assessment = repos.assessments.get("demo-assessment-1") or repos.assessments.create(
        {
            "batchId": batch["id"],
            "title": "Week 6 assessment",
            "type": "assignment",
            "date": (today - timedelta(days=1)).isoformat(),
            "maxMarks": 100,
            "weightage": 1.0,
            "createdBy": "seed-script",
            "createdAt": utcnow(),
        },
        doc_id="demo-assessment-1",
    )

    for index, student in enumerate(students):
        for session_id, session_date, _ in sessions:
            repos.attendance.set(
                {
                    "sessionId": session_id,
                    "batchId": batch["id"],
                    "studentId": student["id"],
                    "studentName": student.get("name"),
                    "sessionDate": session_date.isoformat(),
                    "status": "present" if index % 2 == 0 else "late",
                    "remarks": None,
                    "markedBy": "demo-trainer",
                    "updatedAt": utcnow(),
                },
                doc_id=f"{session_id}_{student['id']}",
            )
        repos.scores.set(
            {
                "assessmentId": assessment["id"],
                "assessmentName": assessment.get("name"),
                "batchId": batch["id"],
                "studentId": student["id"],
                "studentName": student.get("name"),
                "marks": 72 + index * 8,
                "maxMarks": 100,
                "weightage": 1.0,
                "assessmentDate": assessment.get("date"),
                "recordedBy": "demo-trainer",
                "updatedAt": utcnow(),
            },
            doc_id=f"{assessment['id']}_{student['id']}",
        )


def _seed_placement_catalogue(repos: Repos) -> dict:
    now = utcnow()
    company = repos.companies.get("demo-company") or repos.companies.set(
        {
            "name": "Innovate Labs",
            "industry": "Software",
            "contactPerson": "Hiring Team",
            "contactEmail": "careers@innovatelabs.test",
            "active": True,
            "createdAt": now,
            "updatedAt": now,
            "createdBy": "seed-script",
        },
        doc_id="demo-company",
    )
    today = date.today()
    drive = repos.drives.get("demo-drive") or repos.drives.set(
        {
            "companyId": company["id"],
            "companyName": company["name"],
            "role": "Graduate Software Engineer",
            "ctc": 12.0,
            "location": "Pune",
            "driveDate": (today + timedelta(days=21)).isoformat(),
            "deadline": (today + timedelta(days=14)).isoformat(),
            "rounds": [{"name": "Aptitude"}, {"name": "Technical"}, {"name": "HR"}],
            "eligibility": {
                "minCgpa": 6.0,
                "minAttendance": 70.0,
                "minAssessmentAvg": 0.0,
                "batchIds": [],
                "collegeIds": [],
                "branches": [],
            },
            "collegeIds": [],
            "status": "open",
            "allowDreamOffer": False,
            "createdBy": "seed-script",
            "createdAt": now,
            "updatedAt": now,
        },
        doc_id="demo-drive",
    )
    return {"company": company, "drive": drive}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Seed SPMS reference/demo data")
    parser.add_argument("--demo", action="store_true", help="also create demo users and activity")
    parser.add_argument("--password", default=os.getenv("SEED_PASSWORD"))
    parser.add_argument("--email-domain", default="demo.spms.test")
    args = parser.parse_args(argv)

    store = get_store()
    repos = Repos(store)
    users = UsersService(repos)
    metrics = MetricsService(repos)

    if isinstance(store, MemoryStore):
        print(
            "WARNING: USE_FIREBASE=false uses an in-memory store; seeded data disappears\n"
            "         when this process exits. Set USE_FIREBASE=true (emulator or project)\n"
            "         to persist data.",
            file=sys.stderr,
        )

    generated_password = False
    password = args.password
    if not password:
        password = secrets.token_urlsafe(12)
        generated_password = True

    _heading("Reference data")
    college = _ensure_college(repos)
    batch = _ensure_batch(repos, college)
    print(f"college: {college['id']} ({college['name']})")
    print(f"batch:   {batch['id']} ({batch['name']})")

    actor = Principal(
        uid="seed-script",
        role=Role.ADMIN,
        college_ids=[],
        super_admin=True,
        name="Seed Script",
        email="seed@spms.test",
    )

    created_accounts: list[tuple[str, str, str]] = []

    if args.demo:
        _heading("Demo accounts")
        trainer, created = _ensure_account(
            users,
            repos,
            actor,
            email=f"trainer@{args.email_domain}",
            name="Demo Trainer",
            role=Role.TRAINER,
            college_id=college["id"],
            password=password,
        )
        if created:
            created_accounts.append((trainer["email"], "trainer", password))

        current_batch = repos.batches.require(batch["id"])
        if trainer["id"] not in (current_batch.get("trainerIds") or []):
            repos.batches.update(
                batch["id"],
                {
                    "trainerIds": [*(current_batch.get("trainerIds") or []), trainer["id"]],
                    "trainerNames": [*(current_batch.get("trainerNames") or []), trainer["name"]],
                },
            )

        for index in (1, 2):
            student, created = _ensure_account(
                users,
                repos,
                actor,
                email=f"student{index}@{args.email_domain}",
                name=f"Demo Student {index}",
                role=Role.STUDENT,
                college_id=college["id"],
                password=password,
                student_profile=True,
                batch_id=batch["id"],
                roll_no=f"DEMO-{index:03d}",
                degree="B.Tech",
                branch="CSE",
                grad_year=date.today().year + 1,
                cgpa=7.5 + index / 10,
                skills=["python", "sql", "react", "communication"],
            )
            if created:
                created_accounts.append((student["email"], "student", password))

        students = repos.students.for_batch(batch["id"])
        _heading("Demo activity")
        _seed_activity(repos, batch, students)
        for student in students:
            metrics.refresh_student(student["id"])
        repos.batches.update(batch["id"], {"studentCount": len(students)})
        print(f"sessions, attendance and scores for {len(students)} student(s)")

        catalogue = _seed_placement_catalogue(repos)
        print(f"company: {catalogue['company']['id']} ({catalogue['company']['name']})")
        print(f"drive:   {catalogue['drive']['id']} ({catalogue['drive']['role']})")

    _heading("Done")
    if created_accounts:
        print("Created accounts (store these passwords securely; they are shown once):")
        for email, role, pwd in created_accounts:
            print(f"  {role:<8} {email:<35} {pwd}")
        if generated_password:
            print("Password was generated by this script. Pass --password or SEED_PASSWORD to choose your own.")
    else:
        print("No new accounts were created (existing emails were reused).")
    print(
        "\nNext: create an administrator with\n"
        "  .venv/bin/python scripts/create_super_admin.py --email admin@spms.test"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
