"""CSV and PDF report exports (FR-36)."""

from __future__ import annotations

import csv
import io
from datetime import date
from typing import Any, Iterable

from app.core.scoping import ensure_college, scoped_college_ids
from app.core.security import Principal
from app.models.enums import ApplicationStatus, PlacementStatus, Role
from app.repositories import Repos
from app.services.analytics import AnalyticsService


class ReportsService:
    def __init__(self, repos: Repos, analytics: AnalyticsService | None = None) -> None:
        self.repos = repos
        self.analytics = analytics or AnalyticsService(repos)

    def export(
        self,
        actor: Principal,
        *,
        report: str,
        fmt: str,
        college_id: str | None = None,
        batch_id: str | None = None,
    ) -> tuple[bytes, str, str]:
        if not actor.is_admin:
            from app.core.errors import Forbidden

            raise Forbidden("Only admins can export reports", code="role_forbidden")

        students = self._students(actor, college_id, batch_id)
        generated = date.today().isoformat()

        if fmt == "pdf":
            content = self._pdf(actor, report, students, generated)
            return content, "application/pdf", f"spms-{report}-{generated}.pdf"

        rows = self._rows(actor, report, students)
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=list(rows[0].keys()) if rows else ["message"])
        writer.writeheader()
        if rows:
            writer.writerows(rows)
        else:
            writer.writerow({"message": "No data"})
        return buffer.getvalue().encode("utf-8"), "text/csv", f"spms-{report}-{generated}.csv"

    # -- data ---------------------------------------------------------------
    def _students(
        self, actor: Principal, college_id: str | None, batch_id: str | None
    ) -> list[dict[str, Any]]:
        if college_id:
            ensure_college(actor, college_id)
            students = self.repos.students.for_college(college_id, limit=20000)
        else:
            allowed = scoped_college_ids(actor)
            if allowed is None:
                students = self.repos.students.all(cap=20000)
            else:
                students = []
                for cid in allowed:
                    students.extend(self.repos.students.for_college(cid, limit=20000))
        if batch_id:
            students = [s for s in students if s.get("batchId") == batch_id]
        return students

    def _rows(
        self, actor: Principal, report: str, students: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        if report == "placements":
            return [
                {
                    "college": s.get("collegeName") or s.get("collegeId"),
                    "batch": s.get("batchName") or "",
                    "student": s.get("name"),
                    "email": s.get("email"),
                    "branch": s.get("branch") or "",
                    "cgpa": s.get("cgpa") or "",
                    "attendancePct": s.get("attendancePct") or 0,
                    "readinessScore": s.get("readinessScore") or 0,
                    "placementStatus": s.get("placementStatus"),
                    "company": s.get("placedCompany") or "",
                    "ctc": s.get("placedCtc") or "",
                }
                for s in students
            ]

        if report == "students":
            return [
                {
                    "college": s.get("collegeName") or s.get("collegeId"),
                    "batch": s.get("batchName") or "",
                    "rollNo": s.get("rollNo") or "",
                    "name": s.get("name"),
                    "email": s.get("email"),
                    "phone": s.get("phone") or "",
                    "degree": s.get("degree") or "",
                    "branch": s.get("branch") or "",
                    "gradYear": s.get("gradYear") or "",
                    "cgpa": s.get("cgpa") or "",
                    "skills": ";".join(s.get("skills") or []),
                    "attendancePct": s.get("attendancePct") or 0,
                    "assessmentAvg": s.get("assessmentAvg") or 0,
                    "interviewAvg": s.get("interviewAvg") or 0,
                    "profileScore": s.get("profileScore") or 0,
                    "readinessScore": s.get("readinessScore") or 0,
                    "placementStatus": s.get("placementStatus"),
                }
                for s in students
            ]

        if report == "applications":
            student_map = {s["id"]: s for s in students}
            rows = []
            for application in self.repos.applications.all(cap=20000):
                student = student_map.get(application.get("studentId"))
                if student is None:
                    continue
                offer = application.get("offer") or {}
                rows.append(
                    {
                        "company": application.get("companyName") or "",
                        "role": application.get("driveRole") or "",
                        "student": application.get("studentName"),
                        "college": student.get("collegeName") or "",
                        "batch": student.get("batchName") or "",
                        "status": application.get("status"),
                        "ctc": offer.get("ctc") or "",
                        "appliedAt": application.get("appliedAt"),
                    }
                )
            return rows

        if report == "attendance":
            rows = []
            for student in students:
                records = self.repos.attendance.for_student(student["id"])
                counts = {"present": 0, "absent": 0, "late": 0, "excused": 0}
                for record in records:
                    if record.get("status") in counts:
                        counts[record["status"]] += 1
                rows.append(
                    {
                        "college": student.get("collegeName") or "",
                        "batch": student.get("batchName") or "",
                        "student": student.get("name"),
                        "present": counts["present"],
                        "absent": counts["absent"],
                        "late": counts["late"],
                        "excused": counts["excused"],
                        "total": sum(counts.values()),
                        "percentage": student.get("attendancePct") or 0,
                    }
                )
            return rows

        if report == "drives":
            allowed = scoped_college_ids(actor)
            rows = []
            for drive in self.repos.drives.all(cap=5000):
                drive_colleges = drive.get("collegeIds") or []
                if allowed is not None and drive_colleges and not set(allowed).intersection(drive_colleges):
                    continue
                applications = self.repos.applications.for_drive(drive["id"], limit=5000)
                selected = sum(
                    1 for a in applications if a.get("status") == ApplicationStatus.SELECTED.value
                )
                rows.append(
                    {
                        "company": drive.get("companyName") or "",
                        "role": drive.get("role"),
                        "ctc": drive.get("ctc"),
                        "location": drive.get("location") or "",
                        "driveDate": drive.get("driveDate"),
                        "deadline": drive.get("deadline"),
                        "status": drive.get("status"),
                        "applications": len(applications),
                        "selected": selected,
                    }
                )
            return rows

        from app.core.errors import BadRequest

        raise BadRequest(f"Unknown report '{report}'. Use placements, students, applications, attendance or drives")

    # -- PDF ----------------------------------------------------------------
    def _pdf(
        self, actor: Principal, report: str, students: list[dict[str, Any]], generated: str
    ) -> bytes:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=landscape(A4),
            leftMargin=12 * mm,
            rightMargin=12 * mm,
            topMargin=12 * mm,
            bottomMargin=12 * mm,
            title=f"SPMS {report} report",
        )
        styles = getSampleStyleSheet()
        story: list[Any] = [
            Paragraph(f"SPMS — {report.title()} report", styles["Title"]),
            Paragraph(f"Generated {generated}", styles["Normal"]),
            Spacer(1, 6 * mm),
        ]

        if report == "placements":
            metrics = self.analytics.placements(actor)
            summary = [
                ["Students", "Placed", "Placement rate", "Average CTC", "Highest CTC"],
                [
                    metrics["students"],
                    metrics["placed"],
                    f"{metrics['placementRate']}%",
                    f"{metrics['averagePackage']} LPA",
                    f"{metrics['highestPackage']} LPA",
                ],
            ]
            table = Table(summary, hAlign="LEFT")
            table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e293b")),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                        ("FONTSIZE", (0, 0), (-1, -1), 9),
                        ("PADDING", (0, 0), (-1, -1), 5),
                    ]
                )
            )
            story.extend([table, Spacer(1, 6 * mm)])

        headers = ["College", "Batch", "Student", "Branch", "Attendance", "Readiness", "Status"]
        data = [headers] + [
            [
                s.get("collegeName") or "",
                s.get("batchName") or "",
                s.get("name") or "",
                s.get("branch") or "",
                f"{s.get('attendancePct') or 0}%",
                str(s.get("readinessScore") or 0),
                (s.get("placementStatus") or "").replace("_", " "),
            ]
            for s in students[:500]
        ]
        if len(data) == 1:
            data.append(["No data", "", "", "", "", "", ""])

        table = Table(data, repeatRows=1)
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e293b")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("GRID", (0, 0), (-1, -1), 0.3, colors.lightgrey),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f1f5f9")]),
                ]
            )
        )
        story.append(table)
        story.append(Spacer(1, 4 * mm))
        story.append(
            Paragraph(
                f"{len(students)} students in scope. Showing up to 500 rows.", styles["Italic"]
            )
        )
        doc.build(story)
        return buffer.getvalue()
