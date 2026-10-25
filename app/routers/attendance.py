"""Attendance endpoints (FR-15 to FR-18)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status

from app.core.security import Principal, get_current_user, require_staff
from app.models.attendance import (
    AttendanceBulkRequest,
    AttendanceCorrection,
    AttendanceRecord,
    BatchAttendanceSummary,
    Session,
    SessionCreate,
    StudentAttendance,
)
from app.models.common import PageResponse
from app.routers.deps import as_page, get_attendance_service
from app.services.attendance import AttendanceService

router = APIRouter(tags=["attendance"])


@router.post(
    "/batches/{batch_id}/sessions", response_model=Session, status_code=status.HTTP_201_CREATED
)
def create_session(
    batch_id: str,
    payload: SessionCreate,
    user: Principal = Depends(require_staff),
    service: AttendanceService = Depends(get_attendance_service),
) -> dict:
    return service.create_session(user, batch_id, payload)


@router.get("/batches/{batch_id}/sessions", response_model=PageResponse[Session])
def list_sessions(
    batch_id: str,
    limit: int | None = Query(None, ge=1, le=100),
    cursor: str | None = Query(None),
    user: Principal = Depends(get_current_user),
    service: AttendanceService = Depends(get_attendance_service),
) -> dict:
    return as_page(service.list_sessions(user, batch_id, limit=limit, cursor=cursor))


@router.post("/sessions/{session_id}/attendance")
def mark_attendance(
    session_id: str,
    payload: AttendanceBulkRequest,
    user: Principal = Depends(require_staff),
    service: AttendanceService = Depends(get_attendance_service),
) -> dict:
    return service.mark_attendance(user, session_id, payload)


@router.patch("/attendance/{attendance_id}", response_model=AttendanceRecord)
def correct_attendance(
    attendance_id: str,
    payload: AttendanceCorrection,
    user: Principal = Depends(require_staff),
    service: AttendanceService = Depends(get_attendance_service),
) -> dict:
    return service.correct_attendance(user, attendance_id, payload)


@router.get("/students/{student_id}/attendance", response_model=StudentAttendance)
def student_attendance(
    student_id: str,
    user: Principal = Depends(get_current_user),
    service: AttendanceService = Depends(get_attendance_service),
) -> dict:
    return service.student_attendance(user, student_id)


@router.get("/batches/{batch_id}/attendance/summary", response_model=BatchAttendanceSummary)
def batch_attendance_summary(
    batch_id: str,
    user: Principal = Depends(require_staff),
    service: AttendanceService = Depends(get_attendance_service),
) -> dict:
    return service.batch_summary(user, batch_id)
