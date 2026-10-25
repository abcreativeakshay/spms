"""Company, drive and application schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from app.models.common import CamelModel, Eligibility, IsoDate, Offer, Round, RoundResult
from app.models.enums import ApplicationStatus, DriveStatus


class CompanyCreate(CamelModel):
    name: str = Field(min_length=2, max_length=160)
    industry: str | None = None
    contact_person: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    website: str | None = None
    notes: str | None = None
    active: bool = True


class CompanyUpdate(CamelModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    industry: str | None = None
    contact_person: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    website: str | None = None
    notes: str | None = None
    active: bool | None = None


class Company(CamelModel):
    id: str
    name: str
    industry: str | None = None
    contact_person: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    website: str | None = None
    notes: str | None = None
    active: bool = True
    drive_count: int = 0
    created_at: datetime | None = None


class DriveCreate(CamelModel):
    company_id: str
    role: str = Field(min_length=1, max_length=160)
    ctc: float = Field(ge=0, description="CTC in LPA")
    location: str | None = None
    drive_date: IsoDate
    deadline: IsoDate
    rounds: list[Round] = Field(default_factory=list)
    eligibility: Eligibility = Field(default_factory=Eligibility)
    college_ids: list[str] = Field(default_factory=list)
    status: DriveStatus = DriveStatus.DRAFT
    allow_dream_offer: bool = False
    job_description: str | None = None


class DriveUpdate(CamelModel):
    role: str | None = Field(default=None, min_length=1, max_length=160)
    ctc: float | None = Field(default=None, ge=0)
    location: str | None = None
    drive_date: IsoDate | None = None
    deadline: IsoDate | None = None
    rounds: list[Round] | None = None
    eligibility: Eligibility | None = None
    college_ids: list[str] | None = None
    status: DriveStatus | None = None
    allow_dream_offer: bool | None = None
    job_description: str | None = None


class DriveStats(CamelModel):
    eligible: int = 0
    applied: int = 0
    shortlisted: int = 0
    selected: int = 0
    rejected: int = 0
    withdrawn: int = 0


class Drive(CamelModel):
    id: str
    company_id: str
    company_name: str | None = None
    role: str
    ctc: float
    location: str | None = None
    drive_date: IsoDate
    deadline: IsoDate
    rounds: list[Round] = Field(default_factory=list)
    eligibility: Eligibility = Field(default_factory=Eligibility)
    college_ids: list[str] = Field(default_factory=list)
    status: DriveStatus = DriveStatus.DRAFT
    allow_dream_offer: bool = False
    job_description: str | None = None
    stats: DriveStats = Field(default_factory=DriveStats)
    created_by: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class EligibilityResult(CamelModel):
    student_id: str
    student_name: str
    college_id: str
    batch_id: str | None = None
    cgpa: float | None = None
    attendance_pct: float = 0.0
    assessment_avg: float = 0.0
    readiness_score: float = 0.0
    eligible: bool
    reasons: list[str] = Field(default_factory=list)
    applied: bool = False


class DriveForStudent(CamelModel):
    drive: Drive
    eligibility: EligibilityResult
    application: "Application | None" = None


class DriveListItem(Drive):
    eligibility_result: EligibilityResult | None = None
    application: "Application | None" = None


class EligibleStudentsResponse(CamelModel):
    items: list[EligibilityResult]
    total: int = 0
    eligible: int = 0


class ApplyRequest(CamelModel):
    cover_note: str | None = Field(default=None, max_length=1000)


class Application(CamelModel):
    id: str
    drive_id: str
    drive_role: str | None = None
    company_name: str | None = None
    student_id: str
    student_name: str
    student_email: str | None = None
    college_id: str
    batch_id: str | None = None
    batch_name: str | None = None
    status: ApplicationStatus
    current_round: str | None = None
    round_results: list[RoundResult] = Field(default_factory=list)
    offer: Offer | None = None
    cover_note: str | None = None
    applied_at: datetime | None = None
    updated_at: datetime | None = None
    eligibility_snapshot: EligibilityResult | None = None


class RoundUpdate(CamelModel):
    round_name: str = Field(min_length=1, max_length=120)
    status: str
    score: float | None = Field(default=None, ge=0)
    remarks: str | None = None


class OutcomeUpdate(CamelModel):
    outcome: Literal["selected", "rejected", "withdrawn"]
    ctc: float | None = Field(default=None, ge=0)
    offer_date: IsoDate | None = None
    notes: str | None = None
    override_lock: bool = False


class OfferLetterResponse(CamelModel):
    offer_letter_path: str
    offer_letter_url: str


class ApplicationStats(CamelModel):
    total: int = 0
    applied: int = 0
    shortlisted: int = 0
    in_process: int = 0
    selected: int = 0
    rejected: int = 0
    withdrawn: int = 0


DriveForStudent.model_rebuild()
