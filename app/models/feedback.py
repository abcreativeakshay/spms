"""Feedback, notification and audit schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field

from app.models.common import CamelModel, IsoDate, Ratings
from app.models.enums import InterviewType, NotificationType, Recommendation


# --------------------------------------------------------------------------- #
# Interview feedback
# --------------------------------------------------------------------------- #
class FeedbackCreate(CamelModel):
    student_id: str
    interview_type: InterviewType
    drive_id: str | None = None
    date: IsoDate
    ratings: Ratings
    strengths: str | None = Field(default=None, max_length=2000)
    improvements: str | None = Field(default=None, max_length=2000)
    recommendation: Recommendation
    internal_notes: str | None = Field(default=None, max_length=4000)


class Feedback(CamelModel):
    id: str
    student_id: str
    student_name: str | None = None
    batch_id: str | None = None
    college_id: str | None = None
    interview_type: InterviewType
    drive_id: str | None = None
    date: IsoDate
    ratings: Ratings
    average_rating: float = 0.0
    strengths: str | None = None
    improvements: str | None = None
    recommendation: Recommendation
    internal_notes: str | None = None
    given_by: str
    given_by_name: str | None = None
    created_at: datetime | None = None


# --------------------------------------------------------------------------- #
# Notifications
# --------------------------------------------------------------------------- #
class Notification(CamelModel):
    id: str
    user_id: str
    type: NotificationType
    title: str
    body: str
    read: bool = False
    link: str | None = None
    created_at: datetime | None = None


# --------------------------------------------------------------------------- #
# Audit
# --------------------------------------------------------------------------- #
class AuditLog(CamelModel):
    id: str
    actor_id: str
    actor_name: str | None = None
    action: str
    entity: str
    entity_id: str
    college_id: str | None = None
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None
    timestamp: datetime | None = None
    request_id: str | None = None
