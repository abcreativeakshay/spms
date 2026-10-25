"""Derived student metrics: profile completeness, aggregates and readiness score.

All writes are denormalized onto the student document so dashboards and list
endpoints read a single document (PRD §7, §8 performance notes).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.core.config import settings
from app.models.enums import ATTENDANCE_PRESENT_VALUES, PlacementStatus
from app.repositories import Repos


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def ratio(numerator: float, denominator: float, *, digits: int = 1) -> float:
    if not denominator:
        return 0.0
    return round(numerator / denominator * 100, digits)


def compute_profile_score(student: dict[str, Any]) -> int:
    """0-100 completeness score (FR-12)."""
    score = 0.0
    if student.get("name") and student.get("email"):
        score += 5
    if student.get("phone"):
        score += 5
    academic = ["rollNo", "degree", "branch", "gradYear"]
    score += 10 * (sum(1 for field in academic if student.get(field)) / len(academic))
    if student.get("cgpa") is not None:
        score += 10
    score += 15 * min(len(student.get("skills") or []), 3) / 3
    if student.get("projects"):
        score += 15
    if student.get("certifications"):
        score += 10
    links = student.get("links") or {}
    score += 5 if links.get("github") else 0
    score += 5 if links.get("linkedin") else 0
    if student.get("resumePath"):
        score += 20
    return int(round(min(score, 100)))


def attendance_percentage(records: list[dict[str, Any]]) -> tuple[float, dict[str, int]]:
    counts = {"present": 0, "absent": 0, "late": 0, "excused": 0}
    for record in records:
        status = record.get("status")
        if status in counts:
            counts[status] += 1
    total = sum(counts.values())
    credited = sum(counts[s] for s in ATTENDANCE_PRESENT_VALUES)
    return ratio(credited, total), counts


def assessment_average(scores: list[dict[str, Any]]) -> float:
    """Weighted average percentage across scored assessments (FR-35)."""
    weighted = 0.0
    weights = 0.0
    for score in scores:
        max_marks = float(score.get("maxMarks") or 0)
        if max_marks <= 0:
            continue
        weight = float(score.get("weightage") or 1.0)
        weighted += (float(score.get("marks") or 0) / max_marks * 100) * weight
        weights += weight
    if not weights:
        return 0.0
    return round(weighted / weights, 1)


def interview_percentage(feedback_docs: list[dict[str, Any]]) -> float:
    """Average of the four 1-5 ratings, normalized to 0-100."""
    values: list[float] = []
    for doc in feedback_docs:
        ratings = doc.get("ratings") or {}
        parts = [
            ratings.get("technical"),
            ratings.get("communication"),
            ratings.get("problemSolving"),
            ratings.get("attitude"),
        ]
        parts = [float(p) for p in parts if p is not None]
        if parts:
            values.append(sum(parts) / len(parts))
    if not values:
        return 0.0
    return round(sum(values) / len(values) * 20, 1)


def readiness_score(
    *,
    attendance: float,
    assessment: float,
    interview: float,
    profile: float,
    has_interview: bool,
) -> tuple[float, dict[str, float]]:
    """Weighted 0-100 readiness. Missing interview data is re-normalized away."""
    weights = dict(settings.readiness_weights)
    components = {
        "attendance": max(0.0, min(attendance, 100.0)),
        "assessment": max(0.0, min(assessment, 100.0)),
        "interview": max(0.0, min(interview, 100.0)),
        "profile": max(0.0, min(float(profile), 100.0)),
    }
    if not has_interview:
        weights.pop("interview", None)
    total_weight = sum(weights.values()) or 1.0
    score = sum(components[key] * weight for key, weight in weights.items()) / total_weight
    return round(score, 1), weights


class MetricsService:
    def __init__(self, repos: Repos) -> None:
        self.repos = repos

    def refresh_student(self, student_id: str) -> dict[str, Any]:
        student = self.repos.students.require(student_id, "Student")
        attendance_docs = self.repos.attendance.for_student(student_id)
        score_docs = self.repos.scores.for_student(student_id)
        feedback_docs = self.repos.feedback.for_student(student_id)

        attendance_pct, _ = attendance_percentage(attendance_docs)
        assessment_avg = assessment_average(score_docs)
        interview_avg = interview_percentage(feedback_docs)
        profile_score = compute_profile_score(student)
        readiness, _ = readiness_score(
            attendance=attendance_pct,
            assessment=assessment_avg,
            interview=interview_avg,
            profile=profile_score,
            has_interview=bool(feedback_docs),
        )

        batch = self.repos.batches.get(student["batchId"]) if student.get("batchId") else None
        threshold = float(
            (batch or {}).get("minAttendancePct", settings.default_min_attendance_pct)
        )
        at_risk = bool(attendance_docs) and attendance_pct < threshold

        patch = {
            "attendancePct": attendance_pct,
            "assessmentAvg": assessment_avg,
            "interviewAvg": interview_avg,
            "profileScore": profile_score,
            "readinessScore": readiness,
            "atRisk": at_risk,
            "updatedAt": utcnow(),
        }
        self.repos.students.update(student_id, patch)
        return {**student, **patch}

    def refresh_batch(self, batch_id: str) -> None:
        for student in self.repos.students.for_batch(batch_id):
            self.refresh_student(student["id"])

    def readiness_for(self, student: dict[str, Any]) -> tuple[float, dict[str, float]]:
        has_interview = bool(student.get("interviewAvg"))
        return readiness_score(
            attendance=float(student.get("attendancePct") or 0),
            assessment=float(student.get("assessmentAvg") or 0),
            interview=float(student.get("interviewAvg") or 0),
            profile=float(student.get("profileScore") or 0),
            has_interview=has_interview,
        )

    def mark_placed(
        self, student_id: str, *, company: str, ctc: float, lock: bool
    ) -> None:
        self.repos.students.update(
            student_id,
            {
                "placementStatus": PlacementStatus.PLACED.value,
                "placedCompany": company,
                "placedCtc": ctc,
                "placementLocked": lock,
                "updatedAt": utcnow(),
            },
        )
