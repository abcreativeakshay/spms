"""Analytics and reporting schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app.models.common import CamelModel, IsoDate


class TrendPoint(CamelModel):
    label: str
    value: float


class InterviewTrendPoint(CamelModel):
    date: IsoDate
    average: float


class ReadinessBreakdown(CamelModel):
    attendance: float = 0.0
    assessment: float = 0.0
    interview: float = 0.0
    profile: float = 0.0
    weights: dict[str, float] = Field(default_factory=dict)


class StudentAnalytics(CamelModel):
    student_id: str
    name: str
    college_id: str
    batch_id: str | None = None
    attendance_pct: float = 0.0
    assessment_avg: float = 0.0
    interview_avg: float = 0.0
    profile_score: int = 0
    readiness_score: float = 0.0
    readiness: ReadinessBreakdown
    attendance_trend: list[TrendPoint] = Field(default_factory=list)
    score_trend: list[TrendPoint] = Field(default_factory=list)
    interview_trend: list[InterviewTrendPoint] = Field(default_factory=list)
    placement_status: str = "unplaced"
    rank_band: str | None = None
    computed_at: datetime | None = None


class BatchAnalytics(CamelModel):
    batch_id: str
    batch_name: str | None = None
    students: int = 0
    average_attendance: float = 0.0
    average_assessment: float = 0.0
    average_readiness: float = 0.0
    placement_rate: float = 0.0
    at_risk: list[dict] = Field(default_factory=list)
    top_students: list[dict] = Field(default_factory=list)
    attendance_heatmap: list[dict] = Field(default_factory=list)
    assessment_distribution: list[dict] = Field(default_factory=list)
    computed_at: datetime | None = None


class CollegeAnalytics(CamelModel):
    college_id: str
    college_name: str | None = None
    students: int = 0
    placed: int = 0
    placement_rate: float = 0.0
    average_package: float = 0.0
    highest_package: float = 0.0
    average_readiness: float = 0.0
    by_batch: list[dict] = Field(default_factory=list)
    by_branch: list[dict] = Field(default_factory=list)
    by_company: list[dict] = Field(default_factory=list)
    computed_at: datetime | None = None


class PlacementFunnel(CamelModel):
    eligible: int = 0
    applied: int = 0
    shortlisted: int = 0
    selected: int = 0
    conversion_rates: dict[str, float] = Field(default_factory=dict)


class PlacementAnalytics(CamelModel):
    students: int = 0
    placed: int = 0
    placement_rate: float = 0.0
    average_package: float = 0.0
    highest_package: float = 0.0
    median_package: float = 0.0
    time_to_placement_days: float = 0.0
    funnel: PlacementFunnel = Field(default_factory=PlacementFunnel)
    by_college: list[dict] = Field(default_factory=list)
    by_branch: list[dict] = Field(default_factory=list)
    by_company: list[dict] = Field(default_factory=list)
    computed_at: datetime | None = None


class Snapshot(CamelModel):
    id: str
    scope: str
    scope_id: str
    metrics: dict = Field(default_factory=dict)
    computed_at: datetime | None = None
