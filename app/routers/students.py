"""Student profile endpoints (FR-10 to FR-14)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Query, UploadFile, status

from app.core.security import Principal, get_current_user, require_admin
from app.models.common import PageResponse
from app.models.student import ResumeUploadResponse, Student, StudentUpdate
from app.models.user import BulkImportResult
from app.routers.deps import as_page, get_students_service
from app.services.students import StudentsService

router = APIRouter(prefix="/students", tags=["students"])


@router.get("", response_model=PageResponse[Student])
def list_students(
    college_id: str | None = Query(None, alias="collegeId"),
    batch_id: str | None = Query(None, alias="batchId"),
    skills: list[str] | None = Query(None),
    min_cgpa: float | None = Query(None, alias="minCgpa"),
    max_cgpa: float | None = Query(None, alias="maxCgpa"),
    placement_status: str | None = Query(None, alias="placementStatus"),
    at_risk: bool | None = Query(None, alias="atRisk"),
    q: str | None = Query(None),
    limit: int | None = Query(None, ge=1, le=100),
    cursor: str | None = Query(None),
    user: Principal = Depends(get_current_user),
    service: StudentsService = Depends(get_students_service),
) -> dict:
    page = service.list(
        user,
        college_id=college_id,
        batch_id=batch_id,
        skills=skills,
        min_cgpa=min_cgpa,
        max_cgpa=max_cgpa,
        placement_status=placement_status,
        at_risk=at_risk,
        q=q,
        limit=limit,
        cursor=cursor,
    )
    return as_page(page)


@router.get("/me", response_model=Student)
def my_profile(
    user: Principal = Depends(get_current_user),
    service: StudentsService = Depends(get_students_service),
) -> dict:
    return service.me(user)


@router.post("/import", response_model=BulkImportResult)
async def import_students(
    file: UploadFile = File(...),
    send_setup_emails: bool = Query(False, alias="sendSetupEmails"),
    user: Principal = Depends(require_admin),
    service: StudentsService = Depends(get_students_service),
) -> dict:
    data = await file.read()
    result = service.import_students(user, data, send_setup_emails=send_setup_emails)
    return result.model_dump(by_alias=True)


@router.get("/{student_id}", response_model=Student)
def get_student(
    student_id: str,
    user: Principal = Depends(get_current_user),
    service: StudentsService = Depends(get_students_service),
) -> dict:
    return service.get(user, student_id)


@router.patch("/{student_id}", response_model=Student)
def update_student(
    student_id: str,
    payload: StudentUpdate,
    user: Principal = Depends(get_current_user),
    service: StudentsService = Depends(get_students_service),
) -> dict:
    return service.update(user, student_id, payload)


@router.post("/{student_id}/resume", response_model=ResumeUploadResponse)
async def upload_resume(
    student_id: str,
    file: UploadFile = File(...),
    user: Principal = Depends(get_current_user),
    service: StudentsService = Depends(get_students_service),
) -> dict:
    return await service.upload_resume(user, student_id, file)


@router.get("/{student_id}/resume-url")
def resume_url(
    student_id: str,
    user: Principal = Depends(get_current_user),
    service: StudentsService = Depends(get_students_service),
) -> dict:
    return service.resume_url(user, student_id)
