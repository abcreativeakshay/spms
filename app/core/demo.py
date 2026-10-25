"""Deterministic demo dataset for the in-memory store.

Enabled with ``SEED_DEMO=true`` when ``USE_FIREBASE=false``. It exists so the
web client can be explored end-to-end without Firebase credentials:

    SEED_DEMO=true .venv/bin/uvicorn app.main:app --reload --port 8080

Sign in with the development tokens ``dev:demo-admin``, ``dev:demo-trainer``,
``dev:demo-student-1`` or ``dev:demo-student-2``.
"""

from __future__ import annotations

from datetime import date, timedelta

from app.models.enums import Role
from app.repositories import Repos
from app.repositories.store import DocumentStore
from app.core.security import Principal
from app.services.audit import AuditService
from app.services.metrics import MetricsService, utcnow

DEMO_COLLEGE_ID = "college-demo"
DEMO_BATCH_ID = "batch-demo"


def _days(delta: int) -> str:
    return (date.today() + timedelta(days=delta)).isoformat()


def seed_demo_data(store: DocumentStore) -> None:
    repos = Repos(store)
    if repos.colleges.get(DEMO_COLLEGE_ID) is not None:
        return

    now = utcnow()
    repos.colleges.set(
        {
            "name": "Demo Institute of Technology",
            "city": "Pune",
            "contactPerson": "Placement Cell",
            "contactEmail": "placements@demo.spms.test",
            "active": True,
            "createdAt": now,
            "updatedAt": now,
            "createdBy": "seed-demo",
        },
        doc_id=DEMO_COLLEGE_ID,
    )

    users = [
        ("demo-admin", Role.ADMIN, "Demo Admin", "admin@demo.spms.test", [], True),
        ("demo-trainer", Role.TRAINER, "Demo Trainer", "trainer@demo.spms.test", [DEMO_COLLEGE_ID], False),
        ("demo-student-1", Role.STUDENT, "Aarav Sharma", "aarav@demo.spms.test", [DEMO_COLLEGE_ID], False),
        ("demo-student-2", Role.STUDENT, "Diya Patel", "diya@demo.spms.test", [DEMO_COLLEGE_ID], False),
    ]
    for uid, role, name, email, college_ids, super_admin in users:
        repos.users.set(
            {
                "uid": uid,
                "role": role.value,
                "name": name,
                "email": email,
                "collegeIds": college_ids,
                "superAdmin": super_admin,
                "active": True,
                "createdAt": now,
                "updatedAt": now,
            },
            doc_id=uid,
        )

    repos.batches.set(
        {
            "name": "Batch A — Full Stack",
            "course": "Full Stack Engineering",
            "collegeId": DEMO_COLLEGE_ID,
            "collegeName": "Demo Institute of Technology",
            "trainerIds": ["demo-trainer"],
            "trainerNames": ["Demo Trainer"],
            "startDate": _days(-45),
            "endDate": _days(135),
            "minAttendancePct": 75.0,
            "status": "active",
            "studentCount": 2,
            "createdAt": now,
            "updatedAt": now,
            "createdBy": "demo-admin",
        },
        doc_id=DEMO_BATCH_ID,
    )

    student_rows = [
        ("demo-student-1", "Aarav Sharma", "aarav@demo.spms.test", "DEMO-001", 8.4, "CSE"),
        ("demo-student-2", "Diya Patel", "diya@demo.spms.test", "DEMO-002", 7.6, "IT"),
    ]
    for uid, name, email, roll, cgpa, branch in student_rows:
        repos.students.set(
            {
                "uid": uid,
                "name": name,
                "email": email,
                "phone": "+91 90000 00000",
                "collegeId": DEMO_COLLEGE_ID,
                "collegeName": "Demo Institute of Technology",
                "batchId": DEMO_BATCH_ID,
                "batchName": "Batch A — Full Stack",
                "rollNo": roll,
                "degree": "B.Tech",
                "branch": branch,
                "gradYear": date.today().year + 1,
                "cgpa": cgpa,
                "skills": ["python", "sql", "react", "docker"],
                "projects": [{"title": "Placement portal", "tech": ["react", "fastapi"]}],
                "certifications": [{"name": "AWS Cloud Practitioner", "issuer": "AWS"}],
                "links": {
                    "github": "https://github.com/demo",
                    "linkedin": "https://linkedin.com/in/demo",
                },
                "resumePath": None,
                "profileScore": 0,
                "placementStatus": "unplaced",
                "placementLocked": False,
                "placedCompany": None,
                "placedCtc": None,
                "attendancePct": 0.0,
                "assessmentAvg": 0.0,
                "interviewAvg": 0.0,
                "readinessScore": 0.0,
                "atRisk": False,
                "createdAt": now,
                "updatedAt": now,
            },
            doc_id=uid,
        )

    sessions = [
        ("demo-session-1", -7, "Python fundamentals"),
        ("demo-session-2", -5, "SQL joins and indexes"),
        ("demo-session-3", -3, "React state and routing"),
        ("demo-session-4", -1, "System design basics"),
    ]
    for session_id, offset, topic in sessions:
        repos.sessions.set(
            {
                "batchId": DEMO_BATCH_ID,
                "date": _days(offset),
                "topic": topic,
                "trainerId": "demo-trainer",
                "trainerName": "Demo Trainer",
                "durationMinutes": 90,
                "marked": True,
                "presentCount": 2,
                "totalCount": 2,
                "createdAt": now,
            },
            doc_id=session_id,
        )

    for student_index, (uid, *_rest) in enumerate(student_rows):
        for session_index, (session_id, offset, _topic) in enumerate(sessions):
            # Diya misses two sessions so the at-risk workflow is visible in the UI.
            if student_index == 1 and session_index in (1, 2):
                status = "absent"
            else:
                status = "present"
            repos.attendance.set(
                {
                    "sessionId": session_id,
                    "batchId": DEMO_BATCH_ID,
                    "studentId": uid,
                    "studentName": _rest[0],
                    "sessionDate": _days(offset),
                    "status": status,
                    "remarks": None,
                    "markedBy": "demo-trainer",
                    "updatedAt": now,
                },
                doc_id=f"{session_id}_{uid}",
            )

    # Keep session counters consistent with the attendance rows above.
    attendance_rows = repos.attendance.all(cap=10000)
    for session_id, _offset, _topic in sessions:
        credited = sum(
            1
            for row in attendance_rows
            if row.get("sessionId") == session_id
            and row.get("status") in ("present", "late", "excused")
        )
        session_doc = repos.sessions.get(session_id)
        session_doc["presentCount"] = credited
        repos.sessions.set(session_doc, doc_id=session_id)

    assessment_ids = ["demo-assessment-1", "demo-assessment-2"]
    for index, assessment_id in enumerate(assessment_ids, start=1):
        repos.assessments.set(
            {
                "batchId": DEMO_BATCH_ID,
                "batchName": "Batch A — Full Stack",
                "collegeId": DEMO_COLLEGE_ID,
                "title": f"Assessment {index}",
                "type": "assignment" if index == 1 else "mock_test",
                "maxMarks": 100,
                "weightage": 1.0,
                "date": _days(-10 + index),
                "description": None,
                "createdBy": "demo-trainer",
                "createdAt": now,
            },
            doc_id=assessment_id,
        )
    marks = {
        "demo-student-1": [82, 88],
        "demo-student-2": [68, 74],
    }
    for uid, values in marks.items():
        for assessment_id, value in zip(assessment_ids, values):
            repos.scores.set(
                {
                    "assessmentId": assessment_id,
                    "assessmentName": repos.assessments.get(assessment_id)["title"],
                    "batchId": DEMO_BATCH_ID,
                    "studentId": uid,
                    "studentName": repos.students.get(uid)["name"],
                    "marks": value,
                    "maxMarks": 100,
                    "weightage": 1.0,
                    "assessmentDate": repos.assessments.get(assessment_id)["date"],
                    "recordedBy": "demo-trainer",
                    "updatedAt": now,
                },
                doc_id=f"{assessment_id}_{uid}",
            )

    repos.feedback.set(
        {
            "studentId": "demo-student-1",
            "studentName": "Aarav Sharma",
            "batchId": DEMO_BATCH_ID,
            "collegeId": DEMO_COLLEGE_ID,
            "interviewType": "mock",
            "driveId": None,
            "date": _days(-4),
            "ratings": {
                "technical": 4,
                "communication": 4,
                "problemSolving": 5,
                "attitude": 4,
            },
            "averageRating": 4.25,
            "strengths": "Strong problem solving and clear explanations.",
            "improvements": "Add measurable impact to project stories.",
            "recommendation": "strong_yes",
            "internalNotes": "Ready for product company interviews.",
            "givenBy": "demo-trainer",
            "givenByName": "Demo Trainer",
            "createdAt": now,
        },
        doc_id="demo-feedback-1",
    )

    repos.companies.set(
        {
            "name": "Innovate Labs",
            "industry": "Software",
            "contactPerson": "Hiring Team",
            "contactEmail": "careers@innovatelabs.test",
            "active": True,
            "createdAt": now,
            "updatedAt": now,
            "createdBy": "demo-admin",
        },
        doc_id="demo-company",
    )
    repos.drives.set(
        {
            "companyId": "demo-company",
            "companyName": "Innovate Labs",
            "role": "Graduate Software Engineer",
            "ctc": 12.0,
            "location": "Pune",
            "driveDate": _days(21),
            "deadline": _days(14),
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
            "jobDescription": "Build and ship customer-facing products with a senior team.",
            "createdBy": "demo-admin",
            "createdAt": now,
            "updatedAt": now,
        },
        doc_id="demo-drive",
    )

    metrics = MetricsService(repos)
    for uid, *_rest in student_rows:
        metrics.refresh_student(uid)

    audit = AuditService(repos)
    trainer = Principal(
        uid="demo-trainer",
        role=Role.TRAINER,
        college_ids=[DEMO_COLLEGE_ID],
        name="Demo Trainer",
        email="trainer@demo.spms.test",
    )
    admin = Principal(
        uid="demo-admin",
        role=Role.ADMIN,
        super_admin=True,
        name="Demo Admin",
        email="admin@demo.spms.test",
    )
    audit.record(
        trainer,
        "attendance.marked",
        "session",
        "demo-session-3",
        after={"marked": True, "presentCount": 1},
    )
    audit.record(
        trainer,
        "scores.saved",
        "assessment",
        "demo-assessment-2",
        after={"scored": len(student_rows)},
    )
    audit.record(
        admin,
        "student.update",
        "student",
        "demo-student-2",
        after={"placementStatus": "unplaced", "atRisk": True},
    )

    for uid in ("demo-student-1", "demo-student-2"):
        repos.notifications.set(
            {
                "userId": uid,
                "type": "drive",
                "title": "New drive: Innovate Labs",
                "body": "Graduate Software Engineer — apply before the deadline.",
                "read": False,
                "link": "/drives",
                "createdAt": now,
            }
        )
