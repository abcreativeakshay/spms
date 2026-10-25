"""Authentication endpoints (FR-1 to FR-3)."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.security import Principal, get_current_user
from app.models.auth import LogoutAllResponse, MeResponse
from app.routers.deps import get_auth_service
from app.services.auth import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me", response_model=MeResponse)
def me(
    user: Principal = Depends(get_current_user),
    service: AuthService = Depends(get_auth_service),
) -> dict:
    return service.me(user)


@router.post("/logout-all", response_model=LogoutAllResponse)
def logout_all(
    user: Principal = Depends(get_current_user),
    service: AuthService = Depends(get_auth_service),
) -> dict:
    return service.logout_all(user)
