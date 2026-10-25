"""Assessment and score endpoints (FR-19 to FR-21)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Query, UploadFile, status

from app.core.security import Principal, get_current_user, require_staff
from app.models.assessment import (
    Assessment,
    AssessmentAnalytics,
    AssessmentCreate,
    AssessmentUpdate,
    Score,
    ScoreBulkRequest,
    StudentScores,
)
from app.models.common import PageResponse
from app.routers.deps import as_page, get_assessments_service
from app.services.assessments import AssessmentsService

router = APIRouter(tags=["assessments"])


@router.get("/assessments", response_model=PageResponse[Assessment])
def list_assessments(
    batch_id: str | None = Query(None, alias="batchId"),
    college_id: str | None = Query(None, alias="collegeId"),
    assessment_type: str | None = Query(None, alias="type"),
    limit: int | None = Query(None, ge=1, le=100),
    cursor: str | None = Query(None),
    user: Principal = Depends(get_current_user),
    service: AssessmentsService = Depends(get_assessments_service),
) -> dict:
    return as_page(
        service.list(
            user,
            batch_id=batch_id,
            college_id=college_id,
            assessment_type=assessment_type,
            limit=limit,
            cursor=cursor,
        )
    )


@router.post("/assessments", response_model=Assessment, status_code=status.HTTP_201_CREATED)
def create_assessment(
    payload: AssessmentCreate,
    user: Principal = Depends(require_staff),
    service: AssessmentsService = Depends(get_assessments_service),
) -> dict:
    return service.create(user, payload)


@router.get("/assessments/{assessment_id}", response_model=Assessment)
def get_assessment(
    assessment_id: str,
    user: Principal = Depends(get_current_user),
    service: AssessmentsService = Depends(get_assessments_service),
) -> dict:
    return service.get(user, assessment_id)


@router.patch("/assessments/{assessment_id}", response_model=Assessment)
def update_assessment(
    assessment_id: str,
    payload: AssessmentUpdate,
    user: Principal = Depends(require_staff),
    service: AssessmentsService = Depends(get_assessments_service),
) -> dict:
    return service.update(user, assessment_id, payload)


@router.post("/assessments/{assessment_id}/scores")
def save_scores(
    assessment_id: str,
    payload: ScoreBulkRequest,
    user: Principal = Depends(require_staff),
    service: AssessmentsService = Depends(get_assessments_service),
) -> dict:
    return service.save_scores(user, assessment_id, payload)


@router.post("/assessments/{assessment_id}/scores/import")
async def import_scores(
    assessment_id: str,
    file: UploadFile = File(...),
    user: Principal = Depends(require_staff),
    service: AssessmentsService = Depends(get_assessments_service),
) -> dict:
    data = await file.read()
    return service.import_scores_csv(user, assessment_id, data)


@router.get("/assessments/{assessment_id}/scores", response_model=list[Score])
def list_scores(
    assessment_id: str,
    user: Principal = Depends(require_staff),
    service: AssessmentsService = Depends(get_assessments_service),
) -> list[dict]:
    return service.list_scores(user, assessment_id)


@router.get("/assessments/{assessment_id}/analytics", response_model=AssessmentAnalytics)
def assessment_analytics(
    assessment_id: str,
    user: Principal = Depends(require_staff),
    service: AssessmentsService = Depends(get_assessments_service),
) -> dict:
    return service.analytics(user, assessment_id)


@router.get("/students/{student_id}/scores", response_model=StudentScores)
def student_scores(
    student_id: str,
    user: Principal = Depends(get_current_user),
    service: AssessmentsService = Depends(get_assessments_service),
) -> dict:
    return service.student_scores(user, student_id)
