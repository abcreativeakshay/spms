"""College endpoints (FR-7)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status

from app.core.security import Principal, get_current_user, require_admin
from app.models.common import PageResponse
from app.models.student import College, CollegeCreate, CollegeUpdate
from app.routers.deps import as_page, get_colleges_service
from app.services.colleges import CollegesService

router = APIRouter(prefix="/colleges", tags=["colleges"])


@router.get("", response_model=PageResponse[College])
def list_colleges(
    q: str | None = Query(None),
    active: bool | None = Query(None),
    limit: int | None = Query(None, ge=1, le=100),
    cursor: str | None = Query(None),
    user: Principal = Depends(get_current_user),
    service: CollegesService = Depends(get_colleges_service),
) -> dict:
    return as_page(service.list(user, q=q, active=active, limit=limit, cursor=cursor))


@router.post("", response_model=College, status_code=status.HTTP_201_CREATED)
def create_college(
    payload: CollegeCreate,
    user: Principal = Depends(require_admin),
    service: CollegesService = Depends(get_colleges_service),
) -> dict:
    return service.create(user, payload)


@router.get("/{college_id}", response_model=College)
def get_college(
    college_id: str,
    user: Principal = Depends(get_current_user),
    service: CollegesService = Depends(get_colleges_service),
) -> dict:
    return service.get(user, college_id)


@router.patch("/{college_id}", response_model=College)
def update_college(
    college_id: str,
    payload: CollegeUpdate,
    user: Principal = Depends(require_admin),
    service: CollegesService = Depends(get_colleges_service),
) -> dict:
    return service.update(user, college_id, payload)


@router.delete("/{college_id}", response_model=College)
def deactivate_college(
    college_id: str,
    user: Principal = Depends(require_admin),
    service: CollegesService = Depends(get_colleges_service),
) -> dict:
    return service.deactivate(user, college_id)
