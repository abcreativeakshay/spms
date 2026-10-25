"""Interview feedback endpoints (FR-29 to FR-31)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from app.core.security import Principal, get_current_user, require_staff
from app.models.feedback import Feedback, FeedbackCreate
from app.routers.deps import get_feedback_service
from app.services.feedback import FeedbackService

router = APIRouter(tags=["feedback"])


@router.post("/feedback", response_model=Feedback, status_code=status.HTTP_201_CREATED)
def create_feedback(
    payload: FeedbackCreate,
    user: Principal = Depends(require_staff),
    service: FeedbackService = Depends(get_feedback_service),
) -> dict:
    return service.create(user, payload)


@router.get(
    "/students/{student_id}/feedback",
    response_model=list[Feedback],
    response_model_exclude_none=True,
)
def list_feedback(
    student_id: str,
    user: Principal = Depends(get_current_user),
    service: FeedbackService = Depends(get_feedback_service),
) -> list[dict]:
    return service.list_for_student(user, student_id)
