"""Drive endpoints (FR-24 to FR-26)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status

from app.core.security import Principal, get_current_user, require_admin, require_staff
from app.models.common import PageResponse
from app.models.drive import (
    Drive,
    DriveCreate,
    DriveListItem,
    DriveUpdate,
    EligibleStudentsResponse,
)
from app.routers.deps import as_page, get_drives_service
from app.services.drives import DrivesService

router = APIRouter(prefix="/drives", tags=["drives"])


@router.get("", response_model=PageResponse[DriveListItem])
def list_drives(
    status_filter: str | None = Query(None, alias="status"),
    college_id: str | None = Query(None, alias="collegeId"),
    q: str | None = Query(None),
    limit: int | None = Query(None, ge=1, le=100),
    cursor: str | None = Query(None),
    user: Principal = Depends(get_current_user),
    service: DrivesService = Depends(get_drives_service),
) -> dict:
    return as_page(
        service.list(
            user, status=status_filter, college_id=college_id, q=q, limit=limit, cursor=cursor
        )
    )


@router.post("", response_model=Drive, status_code=status.HTTP_201_CREATED)
def create_drive(
    payload: DriveCreate,
    user: Principal = Depends(require_admin),
    service: DrivesService = Depends(get_drives_service),
) -> dict:
    return service.create(user, payload)


@router.get("/{drive_id}", response_model=DriveListItem)
def get_drive(
    drive_id: str,
    user: Principal = Depends(get_current_user),
    service: DrivesService = Depends(get_drives_service),
) -> dict:
    return service.get(user, drive_id)


@router.patch("/{drive_id}", response_model=Drive)
def update_drive(
    drive_id: str,
    payload: DriveUpdate,
    user: Principal = Depends(require_admin),
    service: DrivesService = Depends(get_drives_service),
) -> dict:
    return service.update(user, drive_id, payload)


@router.get("/{drive_id}/eligible-students", response_model=EligibleStudentsResponse)
def eligible_students(
    drive_id: str,
    only_eligible: bool = Query(True, alias="onlyEligible"),
    limit: int = Query(100, ge=1, le=1000),
    user: Principal = Depends(require_staff),
    service: DrivesService = Depends(get_drives_service),
) -> dict:
    return service.eligible_students(user, drive_id, only_eligible=only_eligible, limit=limit)
