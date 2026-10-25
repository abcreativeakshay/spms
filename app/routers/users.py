"""User administration endpoints (FR-4, FR-5)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Query, UploadFile, status

from app.core.security import Principal, require_admin
from app.models.user import (
    BulkImportResult,
    User,
    UserCreate,
    UserCreated,
    UserUpdate,
)
from app.core.pagination import Page
from app.models.common import PageResponse
from app.routers.deps import as_page, get_users_service
from app.services.users import UsersService

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=PageResponse[User])
def list_users(
    role: str | None = Query(None),
    college_id: str | None = Query(None, alias="collegeId"),
    active: bool | None = Query(None),
    q: str | None = Query(None),
    limit: int | None = Query(None, ge=1, le=100),
    cursor: str | None = Query(None),
    user: Principal = Depends(require_admin),
    service: UsersService = Depends(get_users_service),
) -> dict:
    page: Page = service.list(
        user, role=role, college_id=college_id, active=active, q=q, limit=limit, cursor=cursor
    )
    return as_page(page)


@router.post("", response_model=UserCreated, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    user: Principal = Depends(require_admin),
    service: UsersService = Depends(get_users_service),
) -> dict:
    doc, setup_link = service.create(user, payload)
    return {"user": doc, "setupLink": setup_link}


@router.post("/bulk", response_model=BulkImportResult)
async def bulk_create_users(
    file: UploadFile = File(...),
    send_setup_emails: bool = Query(False, alias="sendSetupEmails"),
    user: Principal = Depends(require_admin),
    service: UsersService = Depends(get_users_service),
) -> dict:
    data = await file.read()
    return service.bulk_create_bytes(user, data, send_setup_emails=send_setup_emails).model_dump(
        by_alias=True
    )


@router.get("/{uid}", response_model=User)
def get_user(
    uid: str,
    user: Principal = Depends(require_admin),
    service: UsersService = Depends(get_users_service),
) -> dict:
    return service.get(user, uid)


@router.patch("/{uid}", response_model=User)
def update_user(
    uid: str,
    payload: UserUpdate,
    user: Principal = Depends(require_admin),
    service: UsersService = Depends(get_users_service),
) -> dict:
    return service.update(user, uid, payload)


@router.post("/{uid}/disable", response_model=User)
def disable_user(
    uid: str,
    user: Principal = Depends(require_admin),
    service: UsersService = Depends(get_users_service),
) -> dict:
    return service.set_active(user, uid, False)


@router.post("/{uid}/enable", response_model=User)
def enable_user(
    uid: str,
    user: Principal = Depends(require_admin),
    service: UsersService = Depends(get_users_service),
) -> dict:
    return service.set_active(user, uid, True)
