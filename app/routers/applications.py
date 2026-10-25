"""Application endpoints (FR-25 to FR-28)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Query, UploadFile

from app.core.security import Principal, get_current_user, require_admin
from app.models.common import PageResponse
from app.models.drive import (
    Application,
    ApplyRequest,
    OfferLetterResponse,
    OutcomeUpdate,
    RoundUpdate,
)
from app.routers.deps import as_page, get_applications_service
from app.services.applications import ApplicationsService

router = APIRouter(tags=["applications"])


@router.post("/drives/{drive_id}/apply", response_model=Application, status_code=201)
def apply_to_drive(
    drive_id: str,
    payload: ApplyRequest | None = None,
    user: Principal = Depends(get_current_user),
    service: ApplicationsService = Depends(get_applications_service),
) -> dict:
    return service.apply(user, drive_id, cover_note=payload.cover_note if payload else None)


@router.get("/applications", response_model=PageResponse[Application])
def list_applications(
    drive_id: str | None = Query(None, alias="driveId"),
    student_id: str | None = Query(None, alias="studentId"),
    status_filter: str | None = Query(None, alias="status"),
    limit: int | None = Query(None, ge=1, le=100),
    cursor: str | None = Query(None),
    user: Principal = Depends(get_current_user),
    service: ApplicationsService = Depends(get_applications_service),
) -> dict:
    return as_page(
        service.list(
            user,
            drive_id=drive_id,
            student_id=student_id,
            status=status_filter,
            limit=limit,
            cursor=cursor,
        )
    )


@router.get("/applications/{application_id}", response_model=Application)
def get_application(
    application_id: str,
    user: Principal = Depends(get_current_user),
    service: ApplicationsService = Depends(get_applications_service),
) -> dict:
    return service.get(user, application_id)


@router.patch("/applications/{application_id}/round", response_model=Application)
def update_round(
    application_id: str,
    payload: RoundUpdate,
    user: Principal = Depends(require_admin),
    service: ApplicationsService = Depends(get_applications_service),
) -> dict:
    return service.update_round(user, application_id, payload)


@router.patch("/applications/{application_id}/outcome", response_model=Application)
def update_outcome(
    application_id: str,
    payload: OutcomeUpdate,
    user: Principal = Depends(get_current_user),
    service: ApplicationsService = Depends(get_applications_service),
) -> dict:
    return service.update_outcome(user, application_id, payload)


@router.post("/applications/{application_id}/offer-letter", response_model=OfferLetterResponse)
async def upload_offer_letter(
    application_id: str,
    file: UploadFile = File(...),
    user: Principal = Depends(require_admin),
    service: ApplicationsService = Depends(get_applications_service),
) -> dict:
    return await service.upload_offer_letter(user, application_id, file)


@router.get("/applications/{application_id}/offer-letter-url")
def offer_letter_url(
    application_id: str,
    user: Principal = Depends(get_current_user),
    service: ApplicationsService = Depends(get_applications_service),
) -> dict:
    return service.offer_letter_url(user, application_id)
