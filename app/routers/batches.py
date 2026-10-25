"""Batch endpoints (FR-8, FR-9)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status

from app.core.security import Principal, get_current_user, require_admin, require_staff
from app.models.common import PageResponse
from app.models.student import (
    AssignStudentsRequest,
    AssignStudentsResult,
    Batch,
    BatchCreate,
    BatchUpdate,
    Student,
)
from app.routers.deps import as_page, get_batches_service, get_students_service
from app.services.batches import BatchesService
from app.services.students import StudentsService

router = APIRouter(prefix="/batches", tags=["batches"])


@router.get("", response_model=PageResponse[Batch])
def list_batches(
    college_id: str | None = Query(None, alias="collegeId"),
    trainer_id: str | None = Query(None, alias="trainerId"),
    status_filter: str | None = Query(None, alias="status"),
    q: str | None = Query(None),
    limit: int | None = Query(None, ge=1, le=100),
    cursor: str | None = Query(None),
    user: Principal = Depends(get_current_user),
    service: BatchesService = Depends(get_batches_service),
) -> dict:
    return as_page(
        service.list(
            user,
            college_id=college_id,
            trainer_id=trainer_id,
            status=status_filter,
            q=q,
            limit=limit,
            cursor=cursor,
        )
    )


@router.post("", response_model=Batch, status_code=status.HTTP_201_CREATED)
def create_batch(
    payload: BatchCreate,
    user: Principal = Depends(require_admin),
    service: BatchesService = Depends(get_batches_service),
) -> dict:
    return service.create(user, payload)


@router.get("/{batch_id}", response_model=Batch)
def get_batch(
    batch_id: str,
    user: Principal = Depends(get_current_user),
    service: BatchesService = Depends(get_batches_service),
) -> dict:
    return service.get(user, batch_id)


@router.patch("/{batch_id}", response_model=Batch)
def update_batch(
    batch_id: str,
    payload: BatchUpdate,
    user: Principal = Depends(require_admin),
    service: BatchesService = Depends(get_batches_service),
) -> dict:
    return service.update(user, batch_id, payload)


@router.delete("/{batch_id}", response_model=Batch)
def archive_batch(
    batch_id: str,
    user: Principal = Depends(require_admin),
    service: BatchesService = Depends(get_batches_service),
) -> dict:
    return service.archive(user, batch_id)


@router.post("/{batch_id}/students", response_model=AssignStudentsResult)
def assign_students(
    batch_id: str,
    payload: AssignStudentsRequest,
    user: Principal = Depends(require_staff),
    service: BatchesService = Depends(get_batches_service),
) -> dict:
    return service.assign_students(user, batch_id, payload)


@router.get("/{batch_id}/students", response_model=PageResponse[Student])
def list_batch_students(
    batch_id: str,
    limit: int | None = Query(None, ge=1, le=100),
    cursor: str | None = Query(None),
    user: Principal = Depends(require_staff),
    service: StudentsService = Depends(get_students_service),
) -> dict:
    return as_page(service.list(user, batch_id=batch_id, limit=limit, cursor=cursor))
