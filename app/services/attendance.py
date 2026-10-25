"""Attendance: sessions, marking, corrections, summaries (FR-15 to FR-18)."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from app.core.config import settings
from app.core.errors import BadRequest, Forbidden, NotFound
from app.core.pagination import Page
from app.core.scoping import ensure_batch_access
from app.core.security import Principal
from app.models.attendance import AttendanceBulkRequest, AttendanceCorrection, SessionCreate
from app.models.enums import ATTENDANCE_PRESENT_VALUES, AttendanceStatus, NotificationType, Role
from app.repositories import Repos
from app.services.audit import AuditService
from app.services.metrics import MetricsService, attendance_percentage, ratio, utcnow
from app.services.notify import NotificationService


class AttendanceService:
    def __init__(
        self,
        repos: Repos,
        *,
        audit: AuditService | None = None,
        notifications: NotificationService | None = None,
        metrics: MetricsService | None = None,
    ) -> None:
        self.repos = repos
        self.audit = audit or AuditService(repos)
        self.notifications = notifications or NotificationService(repos)
        self.metrics = metrics or MetricsService(repos)

    # -- sessions -----------------------------------------------------------
    def create_session(self, actor: Principal, batch_id: str, payload: SessionCreate) -> dict[str, Any]:
        batch = self._batch(batch_id)
        ensure_batch_access(actor, batch, write=True)

        session = self.repos.sessions.create(
            {
                "batchId": batch_id,
                "date": payload.date,
                "topic": payload.topic,
                "durationMinutes": payload.duration_minutes,
                "trainerId": actor.uid,
                "trainerName": actor.name,
                "presentCount": 0,
                "totalCount": 0,
                "marked": False,
                "createdAt": utcnow(),
            }
        )
        self.audit.record(
            actor, "attendance.session_create", "session", session["id"], after={"date": payload.date}
        )
        return session

    def list_sessions(
        self,
        actor: Principal,
        batch_id: str,
        *,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> Page:
        batch = self._batch(batch_id)
        if actor.role == Role.STUDENT:
            student = self.repos.students.by_uid(actor.uid)
            if not student or student.get("batchId") != batch_id:
                raise Forbidden("You can only view your own batch", code="batch_forbidden")
        else:
            ensure_batch_access(actor, batch)
        return self.repos.sessions.list(
            [("batchId", "==", batch_id)],
            order_by="date",
            descending=True,
            limit=limit,
            cursor=cursor,
        )

    # -- marking ------------------------------------------------------------
    def mark_attendance(
        self, actor: Principal, session_id: str, payload: AttendanceBulkRequest
    ) -> dict[str, Any]:
        session = self._session(session_id)
        batch = self._batch(session["batchId"])
        ensure_batch_access(actor, batch, write=True)

        students = {s["id"]: s for s in self.repos.students.for_batch(batch["id"])}
        seen: set[str] = set()
        for record in payload.records:
            if record.student_id in seen:
                raise BadRequest(f"Duplicate student {record.student_id} in request")
            seen.add(record.student_id)
            if record.student_id not in students:
                raise BadRequest(
                    f"Student {record.student_id} is not in this batch", code="student_batch_mismatch"
                )

        now = utcnow()
        credited = 0
        newly_at_risk: list[dict[str, Any]] = []

        for record in payload.records:
            student = students[record.student_id]
            doc_id = f"{session_id}_{record.student_id}"
            existing = self.repos.attendance.get(doc_id)
            was_at_risk = bool(student.get("atRisk"))
            self.repos.attendance.set(
                {
                    "sessionId": session_id,
                    "sessionDate": session["date"],
                    "batchId": batch["id"],
                    "studentId": record.student_id,
                    "studentName": student.get("name"),
                    "status": record.status.value,
                    "remarks": record.remarks,
                    "markedBy": actor.uid,
                    "createdAt": (existing or {}).get("createdAt", now),
                    "updatedAt": now,
                },
                doc_id=doc_id,
            )
            if record.status.value in ATTENDANCE_PRESENT_VALUES:
                credited += 1
            refreshed = self.metrics.refresh_student(record.student_id)
            if refreshed.get("atRisk") and not was_at_risk:
                newly_at_risk.append(refreshed)

        self.repos.sessions.update(
            session_id,
            {
                "marked": True,
                "presentCount": credited,
                "totalCount": len(payload.records),
                "markedBy": actor.uid,
                "updatedAt": now,
            },
        )

        for student in newly_at_risk:
            self._notify_low_attendance(student, batch)

        self.audit.record(
            actor,
            "attendance.mark",
            "session",
            session_id,
            after={"records": len(payload.records), "present": credited},
        )
        return {
            "sessionId": session_id,
            "marked": len(payload.records),
            "present": credited,
            "total": len(payload.records),
        }

    def correct_attendance(
        self, actor: Principal, attendance_id: str, payload: AttendanceCorrection
    ) -> dict[str, Any]:
        record = self.repos.attendance.get(attendance_id)
        if record is None:
            raise NotFound(f"Attendance record {attendance_id} not found", code="attendance_not_found")
        batch = self._batch(record["batchId"])
        ensure_batch_access(actor, batch, write=True)

        session_date = date.fromisoformat(record["sessionDate"])
        window = settings.attendance_correction_window_days
        if date.today() - session_date > timedelta(days=window):
            raise Forbidden(
                f"Attendance can only be corrected within {window} days of the session",
                code="correction_window_expired",
            )

        before = {"status": record.get("status"), "remarks": record.get("remarks")}
        updated = self.repos.attendance.update(
            attendance_id,
            {
                "status": payload.status.value,
                "remarks": payload.remarks,
                "correctionReason": payload.reason,
                "correctedBy": actor.uid,
                "markedBy": actor.uid,
                "updatedAt": utcnow(),
            },
        )
        self._recount_session(record["sessionId"])
        refreshed = self.metrics.refresh_student(record["studentId"])
        if refreshed.get("atRisk"):
            self._notify_low_attendance(refreshed, batch)

        self.audit.record(
            actor,
            "attendance.correct",
            "attendance",
            attendance_id,
            before=before,
            after={"status": payload.status.value, "remarks": payload.remarks, "reason": payload.reason},
        )
        return updated

    # -- read models --------------------------------------------------------
    def student_attendance(self, actor: Principal, student_id: str) -> dict[str, Any]:
        student = self.repos.students.require(student_id, "Student")
        batch = self.repos.batches.get(student["batchId"]) if student.get("batchId") else None
        self._ensure_student(actor, student, batch)

        records = self.repos.attendance.for_student(student_id)
        records.sort(key=lambda r: r.get("sessionDate") or "", reverse=True)
        percentage, counts = attendance_percentage(records)
        threshold = float(
            (batch or {}).get("minAttendancePct", settings.default_min_attendance_pct)
        )

        sessions = {
            s["id"]: s
            for s in (
                self.repos.sessions.for_batch(student["batchId"]) if student.get("batchId") else []
            )
        }
        history = []
        for record in records:
            session = sessions.get(record["sessionId"], {})
            history.append(
                {
                    "sessionId": record["sessionId"],
                    "date": record.get("sessionDate") or session.get("date"),
                    "topic": session.get("topic", ""),
                    "status": record["status"],
                    "remarks": record.get("remarks"),
                }
            )

        return {
            "studentId": student_id,
            "batchId": student.get("batchId"),
            "present": counts["present"],
            "absent": counts["absent"],
            "late": counts["late"],
            "excused": counts["excused"],
            "total": len(records),
            "percentage": percentage,
            "threshold": threshold,
            "atRisk": bool(records) and percentage < threshold,
            "history": history,
        }

    def batch_summary(self, actor: Principal, batch_id: str) -> dict[str, Any]:
        batch = self._batch(batch_id)
        ensure_batch_access(actor, batch)

        threshold = float(
            batch.get("minAttendancePct", settings.default_min_attendance_pct)
        )
        students = self.repos.students.for_batch(batch_id)
        records = self.repos.attendance.for_batch(batch_id)
        sessions = self.repos.sessions.for_batch(batch_id, limit=2000)

        by_student: dict[str, list[dict[str, Any]]] = {}
        by_session: dict[str, list[dict[str, Any]]] = {}
        for record in records:
            by_student.setdefault(record["studentId"], []).append(record)
            by_session.setdefault(record["sessionId"], []).append(record)

        rows = []
        percentages = []
        for student in students:
            percentage, counts = attendance_percentage(by_student.get(student["id"], []))
            percentages.append(percentage)
            rows.append(
                {
                    "studentId": student["id"],
                    "studentName": student.get("name", ""),
                    "present": counts["present"],
                    "absent": counts["absent"],
                    "late": counts["late"],
                    "excused": counts["excused"],
                    "total": sum(counts.values()),
                    "percentage": percentage,
                    "atRisk": sum(counts.values()) > 0 and percentage < threshold,
                }
            )

        heatmap = []
        for session in sessions:
            entries = by_session.get(session["id"], [])
            if not entries:
                continue
            credited = sum(1 for e in entries if e.get("status") in ATTENDANCE_PRESENT_VALUES)
            heatmap.append(
                {
                    "sessionId": session["id"],
                    "date": session["date"],
                    "topic": session.get("topic"),
                    "percentage": ratio(credited, len(entries)),
                    "present": credited,
                    "total": len(entries),
                }
            )

        return {
            "batchId": batch_id,
            "batchName": batch.get("name"),
            "threshold": threshold,
            "sessions": len(heatmap) or len(sessions),
            "students": rows,
            "averagePercentage": round(sum(percentages) / len(percentages), 1) if percentages else 0.0,
            "atRiskCount": sum(1 for row in rows if row["atRisk"]),
            "heatmap": heatmap,
        }

    # -- helpers ------------------------------------------------------------
    def _batch(self, batch_id: str) -> dict[str, Any]:
        batch = self.repos.batches.get(batch_id)
        if batch is None:
            raise NotFound(f"Batch {batch_id} not found", code="batch_not_found")
        return batch

    def _session(self, session_id: str) -> dict[str, Any]:
        session = self.repos.sessions.get(session_id)
        if session is None:
            raise NotFound(f"Session {session_id} not found", code="session_not_found")
        return session

    def _ensure_student(self, actor: Principal, student: dict[str, Any], batch: dict[str, Any] | None) -> None:
        from app.core.scoping import ensure_student_access

        ensure_student_access(actor, student, batch=batch)

    def _recount_session(self, session_id: str) -> None:
        records = self.repos.attendance.for_session(session_id)
        credited = sum(1 for r in records if r.get("status") in ATTENDANCE_PRESENT_VALUES)
        self.repos.sessions.update(
            session_id,
            {"presentCount": credited, "totalCount": len(records), "marked": bool(records)},
        )

    def _notify_low_attendance(self, student: dict[str, Any], batch: dict[str, Any]) -> None:
        threshold = batch.get("minAttendancePct", settings.default_min_attendance_pct)
        message = (
            f"{student.get('name')} is at {student.get('attendancePct')}% attendance, "
            f"below the {threshold}% minimum for {batch.get('name')}."
        )
        self.notifications.notify(
            [student.get("uid"), *(batch.get("trainerIds") or [])],
            notification_type=NotificationType.ATTENDANCE,
            title="Low attendance alert",
            body=message,
        )
