"""Analytics endpoints (FR-32 to FR-35)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status

from app.core.security import Principal, get_current_user, require_admin, require_staff
from app.models.analytics import (
    BatchAnalytics,
    CollegeAnalytics,
    PlacementAnalytics,
    Snapshot,
    StudentAnalytics,
)
from app.routers.deps import get_analytics_service
from app.services.analytics import AnalyticsService

router = APIRouter(tags=["analytics"])


@router.get("/analytics/student/{student_id}", response_model=StudentAnalytics)
def student_analytics(
    student_id: str,
    snapshot: bool = Query(False, alias="snapshot"),
    user: Principal = Depends(get_current_user),
    service: AnalyticsService = Depends(get_analytics_service),
) -> dict:
    return service.student(user, student_id, use_snapshot=snapshot)


@router.get("/analytics/batch/{batch_id}", response_model=BatchAnalytics)
def batch_analytics(
    batch_id: str,
    snapshot: bool = Query(False, alias="snapshot"),
    user: Principal = Depends(require_staff),
    service: AnalyticsService = Depends(get_analytics_service),
) -> dict:
    return service.batch(user, batch_id, use_snapshot=snapshot)


@router.get("/analytics/placements", response_model=PlacementAnalytics)
def placement_analytics(
    college_id: str | None = Query(None, alias="collegeId"),
    snapshot: bool = Query(False, alias="snapshot"),
    user: Principal = Depends(require_admin),
    service: AnalyticsService = Depends(get_analytics_service),
) -> dict:
    return service.placements(user, college_id=college_id, use_snapshot=snapshot)


@router.get("/analytics/college/{college_id}", response_model=CollegeAnalytics)
def college_analytics(
    college_id: str,
    snapshot: bool = Query(False, alias="snapshot"),
    user: Principal = Depends(require_admin),
    service: AnalyticsService = Depends(get_analytics_service),
) -> dict:
    return service.college(user, college_id, use_snapshot=snapshot)


@router.post(
    "/analytics/{scope}/{scope_id}/snapshot",
    response_model=Snapshot,
    status_code=status.HTTP_201_CREATED,
)
def create_snapshot(
    scope: str,
    scope_id: str,
    user: Principal = Depends(require_admin),
    service: AnalyticsService = Depends(get_analytics_service),
) -> dict:
    return service.create_snapshot(user, scope, scope_id)
