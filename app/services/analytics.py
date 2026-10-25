"""Analytics, readiness score and snapshots (FR-32 to FR-35)."""

from __future__ import annotations

from statistics import median
from typing import Any

from app.core.config import settings
from app.core.errors import NotFound
from app.core.scoping import ensure_batch_access, ensure_college, ensure_student_access, scoped_college_ids
from app.core.security import Principal
from app.models.enums import ATTENDANCE_PRESENT_VALUES, ApplicationStatus, PlacementStatus, Role
from app.repositories import Repos
from app.services.eligibility import evaluate_eligibility
from app.services.metrics import (
    MetricsService,
    assessment_average,
    attendance_percentage,
    interview_percentage,
    ratio,
    readiness_score,
    utcnow,
)


class AnalyticsService:
    def __init__(self, repos: Repos) -> None:
        self.repos = repos
        self.metrics = MetricsService(repos)

    # -- student ------------------------------------------------------------
    def student(self, actor: Principal, student_id: str, *, use_snapshot: bool = False) -> dict[str, Any]:
        if use_snapshot:
            snapshot = self.repos.snapshots.for_scope("student", student_id)
            if snapshot:
                return {**snapshot.get("metrics", {}), "computedAt": snapshot.get("computedAt")}

        student = self.repos.students.require(student_id, "Student")
        batch = self.repos.batches.get(student["batchId"]) if student.get("batchId") else None
        ensure_student_access(actor, student, batch=batch)

        attendance_docs = self.repos.attendance.for_student(student_id)
        score_docs = self.repos.scores.for_student(student_id)
        feedback_docs = self.repos.feedback.for_student(student_id)

        attendance_pct, _ = attendance_percentage(attendance_docs)
        assessment_avg = assessment_average(score_docs)
        interview_avg = interview_percentage(feedback_docs)
        profile_score = int(student.get("profileScore") or 0)
        readiness, used_weights = readiness_score(
            attendance=attendance_pct,
            assessment=assessment_avg,
            interview=interview_avg,
            profile=profile_score,
            has_interview=bool(feedback_docs),
        )

        attendance_by_date: dict[str, list[dict[str, Any]]] = {}
        for record in attendance_docs:
            attendance_by_date.setdefault(record.get("sessionDate") or "", []).append(record)
        attendance_trend = []
        for day in sorted(attendance_by_date):
            credited = sum(
                1 for r in attendance_by_date[day] if r.get("status") in ATTENDANCE_PRESENT_VALUES
            )
            attendance_trend.append(
                {"label": day, "value": ratio(credited, len(attendance_by_date[day]))}
            )

        score_trend = sorted(
            [
                {
                    "label": score.get("assessmentDate") or "",
                    "value": round(
                        float(score.get("marks") or 0)
                        / float(score.get("maxMarks") or 1)
                        * 100,
                        1,
                    ),
                }
                for score in score_docs
                if float(score.get("maxMarks") or 0) > 0
            ],
            key=lambda point: point["label"],
        )

        interview_trend = sorted(
            [
                {"date": doc.get("date"), "average": float(doc.get("averageRating") or 0)}
                for doc in feedback_docs
            ],
            key=lambda point: point["date"] or "",
        )

        rank_band = None
        if batch:
            batch_students = self.repos.students.for_batch(batch["id"])
            higher = sum(
                1
                for peer in batch_students
                if float(peer.get("readinessScore") or 0) > float(student.get("readinessScore") or readiness)
            )
            percentile = higher / max(len(batch_students) - 1, 1)
            rank_band = (
                "top_10_percent"
                if percentile <= 0.1
                else "top_25_percent"
                if percentile <= 0.25
                else "top_50_percent"
                if percentile <= 0.5
                else "bottom_50_percent"
            )

        return {
            "studentId": student_id,
            "name": student.get("name"),
            "collegeId": student.get("collegeId"),
            "batchId": student.get("batchId"),
            "attendancePct": attendance_pct,
            "assessmentAvg": assessment_avg,
            "interviewAvg": interview_avg,
            "profileScore": profile_score,
            "readinessScore": readiness,
            "readiness": {
                "attendance": attendance_pct,
                "assessment": assessment_avg,
                "interview": interview_avg,
                "profile": profile_score,
                "weights": used_weights,
            },
            "attendanceTrend": attendance_trend[-20:],
            "scoreTrend": score_trend[-20:],
            "interviewTrend": interview_trend[-20:],
            "placementStatus": student.get("placementStatus", "unplaced"),
            "rankBand": rank_band,
        }

    # -- batch --------------------------------------------------------------
    def batch(self, actor: Principal, batch_id: str, *, use_snapshot: bool = False) -> dict[str, Any]:
        if use_snapshot:
            snapshot = self.repos.snapshots.for_scope("batch", batch_id)
            if snapshot:
                return {**snapshot.get("metrics", {}), "computedAt": snapshot.get("computedAt")}

        batch = self.repos.batches.get(batch_id)
        if batch is None:
            raise NotFound(f"Batch {batch_id} not found", code="batch_not_found")
        ensure_batch_access(actor, batch)

        students = self.repos.students.for_batch(batch_id)
        attendance_docs = self.repos.attendance.for_batch(batch_id)
        score_docs = self.repos.scores.for_batch(batch_id)
        sessions = {s["id"]: s for s in self.repos.sessions.for_batch(batch_id, limit=2000)}

        attendance_values = [float(s.get("attendancePct") or 0) for s in students if s.get("attendancePct") is not None]
        readiness_values = [float(s.get("readinessScore") or 0) for s in students]
        placed = sum(1 for s in students if s.get("placementStatus") == PlacementStatus.PLACED.value)

        heatmap_map: dict[str, list[dict[str, Any]]] = {}
        for record in attendance_docs:
            heatmap_map.setdefault(record["sessionId"], []).append(record)
        heatmap = []
        for session_id, records in heatmap_map.items():
            session = sessions.get(session_id, {})
            credited = sum(1 for r in records if r.get("status") in ATTENDANCE_PRESENT_VALUES)
            heatmap.append(
                {
                    "sessionId": session_id,
                    "date": session.get("date"),
                    "topic": session.get("topic"),
                    "percentage": ratio(credited, len(records)),
                }
            )
        heatmap.sort(key=lambda row: row.get("date") or "")

        bucketed = [
            {"label": "0-20", "count": 0},
            {"label": "20-40", "count": 0},
            {"label": "40-60", "count": 0},
            {"label": "60-80", "count": 0},
            {"label": "80-100", "count": 0},
        ]
        for score in score_docs:
            max_marks = float(score.get("maxMarks") or 0)
            if max_marks <= 0:
                continue
            pct = float(score.get("marks") or 0) / max_marks * 100
            bucketed[min(int(pct // 20), 4)]["count"] += 1

        at_risk = sorted(
            [
                {
                    "studentId": s["id"],
                    "name": s.get("name"),
                    "attendancePct": s.get("attendancePct", 0),
                    "readinessScore": s.get("readinessScore", 0),
                }
                for s in students
                if s.get("atRisk")
            ],
            key=lambda row: row["attendancePct"],
        )[:10]
        top = sorted(
            [
                {
                    "studentId": s["id"],
                    "name": s.get("name"),
                    "readinessScore": s.get("readinessScore", 0),
                    "assessmentAvg": s.get("assessmentAvg", 0),
                }
                for s in students
            ],
            key=lambda row: row["readinessScore"],
            reverse=True,
        )[:10]

        return {
            "batchId": batch_id,
            "batchName": batch.get("name"),
            "students": len(students),
            "averageAttendance": round(sum(attendance_values) / len(attendance_values), 1)
            if attendance_values
            else 0.0,
            "averageAssessment": round(
                sum(float(s.get("assessmentAvg") or 0) for s in students) / len(students), 1
            )
            if students
            else 0.0,
            "averageReadiness": round(sum(readiness_values) / len(readiness_values), 1)
            if readiness_values
            else 0.0,
            "placementRate": ratio(placed, len(students)),
            "atRisk": at_risk,
            "topStudents": top,
            "attendanceHeatmap": heatmap,
            "assessmentDistribution": bucketed,
        }

    # -- college ------------------------------------------------------------
    def college(self, actor: Principal, college_id: str, *, use_snapshot: bool = False) -> dict[str, Any]:
        if use_snapshot:
            snapshot = self.repos.snapshots.for_scope("college", college_id)
            if snapshot:
                return {**snapshot.get("metrics", {}), "computedAt": snapshot.get("computedAt")}

        college = self.repos.colleges.get(college_id)
        if college is None:
            raise NotFound(f"College {college_id} not found", code="college_not_found")
        ensure_college(actor, college_id)

        students = self.repos.students.for_college(college_id, limit=20000)
        batches = {b["id"]: b for b in self.repos.batches.for_college(college_id, limit=1000)}
        applications = self.repos.applications.all([("collegeId", "==", college_id)], cap=20000)

        placed_students = [s for s in students if s.get("placementStatus") == PlacementStatus.PLACED.value]
        packages = [float(s.get("placedCtc") or 0) for s in placed_students if s.get("placedCtc")]
        selected_apps = [
            a for a in applications if a.get("status") == ApplicationStatus.SELECTED.value
        ]

        by_batch = []
        for batch_id, batch in batches.items():
            batch_students = [s for s in students if s.get("batchId") == batch_id]
            batch_placed = [
                s for s in batch_students if s.get("placementStatus") == PlacementStatus.PLACED.value
            ]
            batch_packages = [float(s.get("placedCtc") or 0) for s in batch_placed if s.get("placedCtc")]
            by_batch.append(
                {
                    "batchId": batch_id,
                    "batchName": batch.get("name"),
                    "students": len(batch_students),
                    "placed": len(batch_placed),
                    "placementRate": ratio(len(batch_placed), len(batch_students)),
                    "averagePackage": round(sum(batch_packages) / len(batch_packages), 2)
                    if batch_packages
                    else 0.0,
                }
            )

        branches: dict[str, list[dict[str, Any]]] = {}
        for student in students:
            branches.setdefault(student.get("branch") or "Unspecified", []).append(student)
        by_branch = []
        for branch, branch_students in sorted(branches.items()):
            branch_placed = [
                s for s in branch_students if s.get("placementStatus") == PlacementStatus.PLACED.value
            ]
            by_branch.append(
                {
                    "branch": branch,
                    "students": len(branch_students),
                    "placed": len(branch_placed),
                    "placementRate": ratio(len(branch_placed), len(branch_students)),
                }
            )

        companies: dict[str, list[float]] = {}
        for application in selected_apps:
            ctc = float((application.get("offer") or {}).get("ctc") or 0)
            companies.setdefault(application.get("companyName") or "Unknown", []).append(ctc)
        by_company = [
            {
                "company": company,
                "offers": len(ctcs),
                "averageCtc": round(sum(ctcs) / len(ctcs), 2) if ctcs else 0.0,
                "highestCtc": max(ctcs) if ctcs else 0.0,
            }
            for company, ctcs in sorted(companies.items(), key=lambda item: len(item[1]), reverse=True)
        ]

        return {
            "collegeId": college_id,
            "collegeName": college.get("name"),
            "students": len(students),
            "placed": len(placed_students),
            "placementRate": ratio(len(placed_students), len(students)),
            "averagePackage": round(sum(packages) / len(packages), 2) if packages else 0.0,
            "highestPackage": max(packages) if packages else 0.0,
            "averageReadiness": round(
                sum(float(s.get("readinessScore") or 0) for s in students) / len(students), 1
            )
            if students
            else 0.0,
            "byBatch": by_batch,
            "byBranch": by_branch,
            "byCompany": by_company,
        }

    # -- placements ---------------------------------------------------------
    def placements(
        self, actor: Principal, *, college_id: str | None = None, use_snapshot: bool = False
    ) -> dict[str, Any]:
        scope_id = college_id or "all"
        if use_snapshot:
            snapshot = self.repos.snapshots.for_scope("placements", scope_id)
            if snapshot:
                return {**snapshot.get("metrics", {}), "computedAt": snapshot.get("computedAt")}

        if college_id:
            ensure_college(actor, college_id)
            students = self.repos.students.for_college(college_id, limit=20000)
            applications = self.repos.applications.all([("collegeId", "==", college_id)], cap=20000)
            drives = self.repos.drives.all(cap=5000)
            drives = [
                d
                for d in drives
                if not d.get("collegeIds") or college_id in (d.get("collegeIds") or [])
            ]
        else:
            allowed = scoped_college_ids(actor)
            if allowed is None:
                students = self.repos.students.all(cap=20000)
                applications = self.repos.applications.all(cap=20000)
                drives = self.repos.drives.all(cap=5000)
            else:
                students = []
                for cid in allowed:
                    students.extend(self.repos.students.for_college(cid, limit=20000))
                applications = []
                for cid in allowed:
                    applications.extend(self.repos.applications.all([("collegeId", "==", cid)], cap=20000))
                drives = [
                    d
                    for d in self.repos.drives.all(cap=5000)
                    if not d.get("collegeIds") or set(allowed).intersection(d.get("collegeIds") or [])
                ]

        drives = [
            d for d in drives if d.get("status") not in {"draft", "cancelled"}
        ]
        placed_students = [s for s in students if s.get("placementStatus") == PlacementStatus.PLACED.value]
        packages = [float(s.get("placedCtc") or 0) for s in placed_students if s.get("placedCtc")]

        applied_ids = {a.get("studentId") for a in applications}
        shortlisted_ids = {
            a.get("studentId")
            for a in applications
            if a.get("status")
            in {
                ApplicationStatus.SHORTLISTED.value,
                ApplicationStatus.IN_PROCESS.value,
                ApplicationStatus.SELECTED.value,
            }
            or any(
                r.get("status") in {"shortlisted", "cleared"}
                for r in (a.get("roundResults") or [])
            )
        }
        selected_ids = {s["id"] for s in placed_students}

        eligible_ids: set[str] = set()
        for student in students:
            for drive in drives:
                if evaluate_eligibility(drive, student)["eligible"]:
                    eligible_ids.add(student["id"])
                    break

        funnel = {
            "eligible": len(eligible_ids),
            "applied": len(applied_ids),
            "shortlisted": len(shortlisted_ids),
            "selected": len(selected_ids),
            "conversionRates": {
                "appliedToEligible": ratio(len(applied_ids), len(eligible_ids)),
                "shortlistedToApplied": ratio(len(shortlisted_ids), len(applied_ids)),
                "selectedToShortlisted": ratio(len(selected_ids), len(shortlisted_ids)),
            },
        }

        by_college: dict[str, list[dict[str, Any]]] = {}
        for student in students:
            by_college.setdefault(student.get("collegeId") or "", []).append(student)
        by_college_rows = []
        for cid, college_students in by_college.items():
            college = self.repos.colleges.get(cid) or {}
            placed = [
                s for s in college_students if s.get("placementStatus") == PlacementStatus.PLACED.value
            ]
            by_college_rows.append(
                {
                    "collegeId": cid,
                    "collegeName": college.get("name"),
                    "students": len(college_students),
                    "placed": len(placed),
                    "placementRate": ratio(len(placed), len(college_students)),
                }
            )

        branches: dict[str, list[dict[str, Any]]] = {}
        for student in students:
            branches.setdefault(student.get("branch") or "Unspecified", []).append(student)
        by_branch = []
        for branch, branch_students in sorted(branches.items()):
            placed = [
                s for s in branch_students if s.get("placementStatus") == PlacementStatus.PLACED.value
            ]
            by_branch.append(
                {
                    "branch": branch,
                    "students": len(branch_students),
                    "placed": len(placed),
                    "placementRate": ratio(len(placed), len(branch_students)),
                }
            )

        companies: dict[str, list[float]] = {}
        selected_apps = [
            a for a in applications if a.get("status") == ApplicationStatus.SELECTED.value
        ]
        for application in selected_apps:
            ctc = float((application.get("offer") or {}).get("ctc") or 0)
            companies.setdefault(application.get("companyName") or "Unknown", []).append(ctc)
        by_company = [
            {
                "company": company,
                "offers": len(ctcs),
                "averageCtc": round(sum(ctcs) / len(ctcs), 2) if ctcs else 0.0,
                "highestCtc": max(ctcs) if ctcs else 0.0,
            }
            for company, ctcs in sorted(companies.items(), key=lambda item: len(item[1]), reverse=True)
        ]

        time_to_placement = []
        for application in selected_apps:
            student = next((s for s in students if s["id"] == application.get("studentId")), None)
            if not student or not student.get("batchId"):
                continue
            batch = self.repos.batches.get(student["batchId"])
            if not batch or not batch.get("startDate"):
                continue
            try:
                from datetime import date, datetime

                start = date.fromisoformat(batch["startDate"])
                updated = application.get("updatedAt")
                end = updated.date() if isinstance(updated, datetime) else date.today()
                days = (end - start).days
                if days >= 0:
                    time_to_placement.append(days)
            except (ValueError, TypeError):
                continue

        return {
            "students": len(students),
            "placed": len(placed_students),
            "placementRate": ratio(len(placed_students), len(students)),
            "averagePackage": round(sum(packages) / len(packages), 2) if packages else 0.0,
            "highestPackage": max(packages) if packages else 0.0,
            "medianPackage": round(median(packages), 2) if packages else 0.0,
            "timeToPlacementDays": round(sum(time_to_placement) / len(time_to_placement), 1)
            if time_to_placement
            else 0.0,
            "funnel": funnel,
            "byCollege": by_college_rows,
            "byBranch": by_branch,
            "byCompany": by_company,
        }

    # -- snapshots ----------------------------------------------------------
    def create_snapshot(self, actor: Principal, scope: str, scope_id: str) -> dict[str, Any]:
        if scope == "student":
            metrics = self.student(actor, scope_id)
        elif scope == "batch":
            metrics = self.batch(actor, scope_id)
        elif scope == "college":
            metrics = self.college(actor, scope_id)
        elif scope == "placements":
            metrics = self.placements(actor)
            scope_id = "all"
        else:
            raise NotFound(f"Unknown analytics scope {scope}", code="invalid_scope")

        existing = self.repos.snapshots.for_scope(scope, scope_id)
        now = utcnow()
        payload = {"scope": scope, "scopeId": scope_id, "metrics": metrics, "computedAt": now}
        if existing:
            snapshot = self.repos.snapshots.update(existing["id"], payload)
        else:
            snapshot = self.repos.snapshots.create(payload)
        return snapshot
