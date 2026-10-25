"""Structured interview feedback (FR-29 to FR-31)."""

from __future__ import annotations

from typing import Any

from app.core.errors import Forbidden, NotFound
from app.core.scoping import ensure_student_access
from app.core.security import Principal
from app.models.enums import NotificationType, Role
from app.models.feedback import FeedbackCreate
from app.repositories import Repos
from app.services.audit import AuditService
from app.services.metrics import MetricsService, utcnow
from app.services.notify import NotificationService


class FeedbackService:
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

    def create(self, actor: Principal, payload: FeedbackCreate) -> dict[str, Any]:
        if actor.role == Role.STUDENT:
            raise Forbidden("Students cannot submit interview feedback", code="role_forbidden")
        student = self.repos.students.require(payload.student_id, "Student")
        batch = self.repos.batches.get(student["batchId"]) if student.get("batchId") else None
        ensure_student_access(actor, student, batch=batch)

        if payload.drive_id and self.repos.drives.get(payload.drive_id) is None:
            raise NotFound(f"Drive {payload.drive_id} not found", code="drive_not_found")

        ratings = payload.ratings.model_dump(by_alias=True)
        feedback = self.repos.feedback.create(
            {
                "studentId": student["id"],
                "studentName": student.get("name"),
                "batchId": student.get("batchId"),
                "collegeId": student.get("collegeId"),
                "interviewType": payload.interview_type.value,
                "driveId": payload.drive_id,
                "date": payload.date,
                "ratings": ratings,
                "averageRating": payload.ratings.average,
                "strengths": payload.strengths,
                "improvements": payload.improvements,
                "recommendation": payload.recommendation.value,
                "internalNotes": payload.internal_notes,
                "givenBy": actor.uid,
                "givenByName": actor.name,
                "createdAt": utcnow(),
            }
        )
        self.metrics.refresh_student(student["id"])
        self.notifications.notify(
            [student.get("uid")],
            notification_type=NotificationType.FEEDBACK,
            title="New interview feedback",
            body=f"{actor.name or 'Your trainer'} added feedback from your {payload.interview_type.value} interview.",
            link="/feedback",
        )
        self.audit.record(
            actor, "feedback.create", "feedback", feedback["id"], after={"studentId": student["id"]}
        )
        return feedback

    def list_for_student(self, actor: Principal, student_id: str) -> list[dict[str, Any]]:
        student = self.repos.students.require(student_id, "Student")
        batch = self.repos.batches.get(student["batchId"]) if student.get("batchId") else None
        ensure_student_access(actor, student, batch=batch)

        docs = self.repos.feedback.for_student(student_id)
        if actor.role == Role.STUDENT:
            # FR-30: internal notes never leave the backend for students.
            return [{k: v for k, v in doc.items() if k != "internalNotes"} for doc in docs]
        return docs
