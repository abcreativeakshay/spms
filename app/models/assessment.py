"""Assessment and score schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app.models.common import CamelModel, IsoDate
from app.models.enums import AssessmentType


class AssessmentCreate(CamelModel):
    batch_id: str
    title: str = Field(min_length=1, max_length=200)
    type: AssessmentType
    max_marks: float = Field(gt=0, le=1000)
    weightage: float = Field(default=1.0, gt=0, le=100)
    date: IsoDate
    description: str | None = None


class AssessmentUpdate(CamelModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    type: AssessmentType | None = None
    max_marks: float | None = Field(default=None, gt=0, le=1000)
    weightage: float | None = Field(default=None, gt=0, le=100)
    date: IsoDate | None = None
    description: str | None = None


class Assessment(CamelModel):
    id: str
    batch_id: str
    batch_name: str | None = None
    college_id: str
    title: str
    type: AssessmentType
    max_marks: float
    weightage: float = 1.0
    date: IsoDate
    description: str | None = None
    created_by: str
    created_at: datetime | None = None
    scored_count: int = 0


class ScoreEntry(CamelModel):
    student_id: str
    marks: float = Field(ge=0)
    remarks: str | None = None


class ScoreBulkRequest(CamelModel):
    records: list[ScoreEntry] = Field(min_length=1)


class Score(CamelModel):
    id: str
    assessment_id: str
    assessment_title: str | None = None
    student_id: str
    student_name: str | None = None
    batch_id: str
    marks: float
    max_marks: float | None = None
    remarks: str | None = None
    updated_by: str | None = None
    updated_at: datetime | None = None


class StudentScoreItem(CamelModel):
    assessment_id: str
    title: str
    type: AssessmentType
    date: IsoDate
    marks: float
    max_marks: float
    percentage: float
    class_average: float
    rank_band: str
    remarks: str | None = None


class StudentScores(CamelModel):
    student_id: str
    overall_average: float = 0.0
    items: list[StudentScoreItem] = Field(default_factory=list)


class ScoreDistributionBucket(CamelModel):
    label: str
    count: int


class AssessmentAnalytics(CamelModel):
    assessment_id: str
    title: str
    batch_id: str
    max_marks: float
    scored: int
    average: float = 0.0
    highest: float = 0.0
    lowest: float = 0.0
    pass_rate: float = 0.0
    distribution: list[ScoreDistributionBucket] = Field(default_factory=list)
