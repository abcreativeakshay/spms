"""College, batch and student schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app.models.common import CamelModel, Certification, IsoDate, Links, Project
from app.models.enums import BatchStatus, PlacementStatus


# --------------------------------------------------------------------------- #
# Colleges
# --------------------------------------------------------------------------- #
class CollegeCreate(CamelModel):
    name: str = Field(min_length=2, max_length=160)
    city: str | None = None
    contact_person: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    active: bool = True


class CollegeUpdate(CamelModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    city: str | None = None
    contact_person: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    active: bool | None = None


class College(CamelModel):
    id: str
    name: str
    city: str | None = None
    contact_person: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    active: bool = True
    student_count: int = 0
    batch_count: int = 0
    created_at: datetime | None = None
    created_by: str | None = None


# --------------------------------------------------------------------------- #
# Batches
# --------------------------------------------------------------------------- #
class BatchCreate(CamelModel):
    name: str = Field(min_length=1, max_length=120)
    course: str = Field(min_length=1, max_length=160)
    college_id: str
    trainer_ids: list[str] = Field(default_factory=list)
    start_date: IsoDate
    end_date: IsoDate
    min_attendance_pct: float = Field(default=75.0, ge=0, le=100)
    status: BatchStatus = BatchStatus.ACTIVE


class BatchUpdate(CamelModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    course: str | None = Field(default=None, min_length=1, max_length=160)
    trainer_ids: list[str] | None = None
    start_date: IsoDate | None = None
    end_date: IsoDate | None = None
    min_attendance_pct: float | None = Field(default=None, ge=0, le=100)
    status: BatchStatus | None = None


class Batch(CamelModel):
    id: str
    name: str
    course: str
    college_id: str
    college_name: str | None = None
    trainer_ids: list[str] = Field(default_factory=list)
    trainer_names: list[str] = Field(default_factory=list)
    start_date: IsoDate
    end_date: IsoDate
    min_attendance_pct: float = 75.0
    status: BatchStatus = BatchStatus.ACTIVE
    student_count: int = 0
    created_at: datetime | None = None
    created_by: str | None = None


class AssignStudentsRequest(CamelModel):
    student_ids: list[str] = Field(min_length=1)
    move: bool = True


class AssignStudentsResult(CamelModel):
    assigned: int
    history_ids: list[str] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Students
# --------------------------------------------------------------------------- #
class StudentUpdate(CamelModel):
    # personal (student-editable)
    name: str | None = Field(default=None, min_length=2, max_length=120)
    phone: str | None = None
    skills: list[str] | None = None
    projects: list[Project] | None = None
    certifications: list[Certification] | None = None
    links: Links | None = None
    # academic (trainer/admin)
    roll_no: str | None = None
    degree: str | None = None
    branch: str | None = None
    grad_year: int | None = Field(default=None, ge=1990, le=2100)
    cgpa: float | None = Field(default=None, ge=0, le=10)
    placement_status: PlacementStatus | None = None
    placement_locked: bool | None = None


class Student(CamelModel):
    id: str
    uid: str
    name: str
    email: str
    phone: str | None = None
    college_id: str
    college_name: str | None = None
    batch_id: str | None = None
    batch_name: str | None = None
    roll_no: str | None = None
    degree: str | None = None
    branch: str | None = None
    grad_year: int | None = None
    cgpa: float | None = None
    skills: list[str] = Field(default_factory=list)
    projects: list[Project] = Field(default_factory=list)
    certifications: list[Certification] = Field(default_factory=list)
    links: Links | None = None
    resume_path: str | None = None
    profile_score: int = 0
    placement_status: PlacementStatus = PlacementStatus.UNPLACED
    placement_locked: bool = False
    placed_company: str | None = None
    placed_ctc: float | None = None
    attendance_pct: float = 0.0
    assessment_avg: float = 0.0
    interview_avg: float = 0.0
    readiness_score: float = 0.0
    at_risk: bool = False
    created_at: datetime | None = None
    updated_at: datetime | None = None


class BatchAssignHistory(CamelModel):
    id: str
    student_id: str
    from_batch_id: str | None = None
    to_batch_id: str
    moved_by: str
    moved_at: datetime | None = None
    reason: str | None = None


class ResumeUploadResponse(CamelModel):
    resume_path: str
    resume_url: str
    profile_score: int
