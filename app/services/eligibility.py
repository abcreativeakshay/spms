"""Eligibility engine (FR-25) and drive CRUD (FR-23, FR-24, FR-27/28 policy)."""

from __future__ import annotations

from typing import Any

from app.core.config import settings
from app.models.enums import DriveStatus, PlacementStatus
from app.services.metrics import readiness_score


def evaluate_eligibility(
    drive: dict[str, Any],
    student: dict[str, Any],
    *,
    applied: bool = False,
    profile_threshold: int | None = None,
) -> dict[str, Any]:
    eligibility = drive.get("eligibility") or {}
    reasons: list[str] = []

    drive_colleges = drive.get("collegeIds") or []
    allowed_colleges = set(drive_colleges) | set(eligibility.get("collegeIds") or [])
    if allowed_colleges and student.get("collegeId") not in allowed_colleges:
        reasons.append("Your college is not in the allowed colleges for this drive")

    batch_ids = eligibility.get("batchIds") or []
    if batch_ids and student.get("batchId") not in batch_ids:
        reasons.append("Your batch is not eligible for this drive")

    branches = eligibility.get("branches") or []
    if branches and (student.get("branch") or "") not in branches:
        reasons.append("Your branch is not eligible for this drive")

    min_cgpa = float(eligibility.get("minCgpa") or 0)
    cgpa = student.get("cgpa")
    if min_cgpa > 0 and (cgpa is None or float(cgpa) < min_cgpa):
        reasons.append(f"CGPA {cgpa if cgpa is not None else 'not set'} is below the {min_cgpa:g} minimum")

    min_attendance = float(eligibility.get("minAttendance") or 0)
    attendance = float(student.get("attendancePct") or 0)
    if min_attendance > 0 and attendance < min_attendance:
        reasons.append(f"Attendance {attendance:g}% is below the {min_attendance:g}% minimum")

    min_assessment = float(eligibility.get("minAssessmentAvg") or 0)
    assessment_avg = float(student.get("assessmentAvg") or 0)
    if min_assessment > 0 and assessment_avg < min_assessment:
        reasons.append(
            f"Assessment average {assessment_avg:g}% is below the {min_assessment:g}% minimum"
        )

    threshold = (
        settings.profile_completeness_threshold if profile_threshold is None else profile_threshold
    )
    profile_score = int(student.get("profileScore") or 0)
    if threshold > 0 and profile_score < threshold:
        reasons.append(
            f"Profile is {profile_score}% complete; {threshold}% is required before applying"
        )

    placed = student.get("placementStatus") == PlacementStatus.PLACED.value
    if placed and (student.get("placementLocked") or not drive.get("allowDreamOffer")):
        if drive.get("allowDreamOffer"):
            reasons.append("You are already placed and the dream-offer override has not been granted")
        else:
            reasons.append(
                "You are already placed; this drive does not allow dream offers"
            )

    readiness, _ = readiness_score(
        attendance=attendance,
        assessment=assessment_avg,
        interview=float(student.get("interviewAvg") or 0),
        profile=profile_score,
        has_interview=bool(student.get("interviewAvg")),
    )

    return {
        "studentId": student["id"],
        "studentName": student.get("name", ""),
        "collegeId": student.get("collegeId"),
        "batchId": student.get("batchId"),
        "cgpa": cgpa,
        "attendancePct": attendance,
        "assessmentAvg": assessment_avg,
        "readinessScore": readiness,
        "eligible": not reasons,
        "reasons": reasons,
        "applied": applied,
    }


def drive_is_open(drive: dict[str, Any], deadline: str | None) -> bool:
    from datetime import date

    if drive.get("status") != DriveStatus.OPEN.value:
        return False
    if not deadline:
        return False
    try:
        return date.fromisoformat(deadline) >= date.today()
    except ValueError:
        return False
