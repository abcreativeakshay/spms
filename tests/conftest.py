"""Shared pytest fixtures: in-memory store, seeded admin, dev tokens."""

from __future__ import annotations

from typing import Any, Iterator

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.repositories.store import MemoryStore, get_store


class Ctx:
    def __init__(self, client: TestClient, store: MemoryStore) -> None:
        self.client = client
        self.store = store

    # -- auth headers -------------------------------------------------------
    @staticmethod
    def headers(uid: str) -> dict[str, str]:
        return {"Authorization": f"Bearer dev:{uid}"}

    # -- direct seeding (bypasses HTTP) ------------------------------------
    def seed_user(
        self,
        uid: str,
        role: str,
        *,
        name: str | None = None,
        email: str | None = None,
        college_ids: list[str] | None = None,
        super_admin: bool = False,
        active: bool = True,
    ) -> dict[str, Any]:
        return self.store.set(
            "users",
            uid,
            {
                "uid": uid,
                "role": role,
                "name": name or f"{role.title()} {uid}",
                "email": email or f"{uid}@spms.test",
                "collegeIds": college_ids or [],
                "superAdmin": super_admin,
                "active": active,
            },
        )

    def seed_college(self, college_id: str = "college-1", name: str = "Test College") -> dict[str, Any]:
        return self.store.set(
            "colleges",
            college_id,
            {"name": name, "city": "Pune", "active": True},
        )

    def seed_batch(
        self, batch_id: str = "batch-1", college_id: str = "college-1", **extra: Any
    ) -> dict[str, Any]:
        doc = {
            "name": "Batch A",
            "course": "Full Stack",
            "collegeId": college_id,
            "collegeName": "Test College",
            "trainerIds": [],
            "trainerNames": [],
            "startDate": "2026-01-05",
            "endDate": "2026-06-30",
            "minAttendancePct": 75.0,
            "status": "active",
            "studentCount": 0,
        }
        doc.update(extra)
        return self.store.set("batches", batch_id, doc)

    def seed_student(
        self,
        student_id: str = "student-1",
        *,
        uid: str | None = None,
        college_id: str = "college-1",
        batch_id: str | None = "batch-1",
        cgpa: float = 8.0,
        **extra: Any,
    ) -> dict[str, Any]:
        uid = uid or f"uid-{student_id}"
        doc = {
            "uid": uid,
            "name": f"Student {student_id}",
            "email": f"{student_id}@spms.test",
            "phone": "+91 90000 00000",
            "collegeId": college_id,
            "collegeName": "Test College",
            "batchId": batch_id,
            "batchName": "Batch A",
            "rollNo": f"R-{student_id}",
            "degree": "B.Tech",
            "branch": "CSE",
            "gradYear": 2026,
            "cgpa": cgpa,
            "skills": ["python", "sql", "react"],
            "projects": [{"title": "Capstone"}],
            "certifications": [{"name": "AWS"}],
            "links": {"github": "https://github.com/x", "linkedin": "https://linkedin.com/in/x"},
            "resumePath": f"resumes/{college_id}/{student_id}/cv.pdf",
            "profileScore": 100,
            "placementStatus": "unplaced",
            "placementLocked": False,
            "attendancePct": 100.0,
            "assessmentAvg": 80.0,
            "interviewAvg": 0.0,
            "readinessScore": 80.0,
            "atRisk": False,
        }
        doc.update(extra)
        return self.store.set("students", student_id, doc)

    def seed_drive(
        self,
        drive_id: str = "drive-1",
        *,
        company_id: str = "company-1",
        **extra: Any,
    ) -> dict[str, Any]:
        doc = {
            "companyId": company_id,
            "companyName": "Acme",
            "role": "SDE",
            "ctc": 12.0,
            "location": "Bengaluru",
            "driveDate": "2026-12-01",
            "deadline": "2026-11-20",
            "rounds": [{"name": "Aptitude"}, {"name": "Interview"}],
            "eligibility": {
                "minCgpa": 6.0,
                "minAttendance": 75.0,
                "minAssessmentAvg": 0.0,
                "batchIds": [],
                "collegeIds": [],
                "branches": [],
            },
            "collegeIds": ["college-1"],
            "status": "open",
            "allowDreamOffer": False,
        }
        doc.update(extra)
        return self.store.set("drives", drive_id, doc)


@pytest.fixture
def ctx() -> Iterator[Ctx]:
    store = MemoryStore()
    settings.use_firebase = False
    app.dependency_overrides[get_store] = lambda: store
    with TestClient(app) as client:
        yield Ctx(client, store)
    app.dependency_overrides.clear()
