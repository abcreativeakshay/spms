"""Enumerations shared by models, services and routers."""

from __future__ import annotations

from enum import Enum


class Role(str, Enum):
    ADMIN = "admin"
    TRAINER = "trainer"
    STUDENT = "student"


class BatchStatus(str, Enum):
    PLANNED = "planned"
    ACTIVE = "active"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class AttendanceStatus(str, Enum):
    PRESENT = "present"
    ABSENT = "absent"
    LATE = "late"
    EXCUSED = "excused"


ATTENDANCE_PRESENT_VALUES = {
    AttendanceStatus.PRESENT.value,
    AttendanceStatus.LATE.value,
    AttendanceStatus.EXCUSED.value,
}


class AssessmentType(str, Enum):
    QUIZ = "quiz"
    ASSIGNMENT = "assignment"
    MOCK_TEST = "mock_test"
    MOCK_INTERVIEW = "mock_interview"
    APTITUDE = "aptitude"


class PlacementStatus(str, Enum):
    UNPLACED = "unplaced"
    IN_PROCESS = "in_process"
    PLACED = "placed"
    OPTED_OUT = "opted_out"


class DriveStatus(str, Enum):
    DRAFT = "draft"
    OPEN = "open"
    CLOSED = "closed"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class ApplicationStatus(str, Enum):
    APPLIED = "applied"
    SHORTLISTED = "shortlisted"
    IN_PROCESS = "in_process"
    SELECTED = "selected"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


class RoundResultStatus(str, Enum):
    SHORTLISTED = "shortlisted"
    CLEARED = "cleared"
    REJECTED = "rejected"
    ABSENT = "absent"


class InterviewType(str, Enum):
    MOCK = "mock"
    REAL = "real"


class Recommendation(str, Enum):
    STRONG_YES = "strong_yes"
    YES = "yes"
    MAYBE = "maybe"
    NO = "no"


class NotificationType(str, Enum):
    DRIVE = "drive"
    DEADLINE = "deadline"
    APPLICATION = "application"
    ATTENDANCE = "attendance"
    FEEDBACK = "feedback"
    SYSTEM = "system"


class SkillMatch(str, Enum):
    """Convenience values for student filters."""


class SortOrder(str, Enum):
    ASC = "asc"
    DESC = "desc"
