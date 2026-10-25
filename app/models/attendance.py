"""Attendance schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app.models.common import CamelModel, IsoDate
from app.models.enums import AttendanceStatus


class SessionCreate(CamelModel):
    date: IsoDate
    topic: str = Field(min_length=1, max_length=200)
    duration_minutes: int | None = Field(default=None, ge=1, le=600)


class Session(CamelModel):
    id: str
    batch_id: str
    date: IsoDate
    topic: str
    trainer_id: str
    trainer_name: str | None = None
    duration_minutes: int | None = None
    marked: bool = False
    present_count: int = 0
    total_count: int = 0
    created_at: datetime | None = None


class AttendanceMark(CamelModel):
    student_id: str
    status: AttendanceStatus
    remarks: str | None = None


class AttendanceBulkRequest(CamelModel):
    records: list[AttendanceMark] = Field(min_length=1)


class AttendanceCorrection(CamelModel):
    status: AttendanceStatus
    remarks: str | None = None
    reason: str = Field(min_length=3, max_length=500)


class AttendanceRecord(CamelModel):
    id: str
    session_id: str
    batch_id: str
    student_id: str
    student_name: str | None = None
    status: AttendanceStatus
    remarks: str | None = None
    marked_by: str
    updated_at: datetime | None = None


class AttendanceHistoryItem(CamelModel):
    session_id: str
    date: IsoDate
    topic: str
    status: AttendanceStatus
    remarks: str | None = None


class StudentAttendance(CamelModel):
    student_id: str
    batch_id: str | None = None
    present: int = 0
    absent: int = 0
    late: int = 0
    excused: int = 0
    total: int = 0
    percentage: float = 0.0
    threshold: float = 75.0
    at_risk: bool = False
    history: list[AttendanceHistoryItem] = Field(default_factory=list)


class AttendanceSummaryRow(CamelModel):
    student_id: str
    student_name: str
    present: int = 0
    absent: int = 0
    late: int = 0
    excused: int = 0
    total: int = 0
    percentage: float = 0.0
    at_risk: bool = False


class BatchAttendanceSummary(CamelModel):
    batch_id: str
    batch_name: str | None = None
    threshold: float
    sessions: int = 0
    students: list[AttendanceSummaryRow] = Field(default_factory=list)
    average_percentage: float = 0.0
    at_risk_count: int = 0
    heatmap: list[dict] = Field(default_factory=list)
