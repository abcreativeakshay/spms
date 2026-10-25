"""Company endpoints (FR-23)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status

from app.core.security import Principal, get_current_user, require_admin
from app.models.common import PageResponse
from app.models.drive import Company, CompanyCreate, CompanyUpdate
from app.routers.deps import as_page, get_companies_service
from app.services.companies import CompaniesService

router = APIRouter(prefix="/companies", tags=["companies"])


@router.get("", response_model=PageResponse[Company])
def list_companies(
    q: str | None = Query(None),
    active: bool | None = Query(None),
    limit: int | None = Query(None, ge=1, le=100),
    cursor: str | None = Query(None),
    user: Principal = Depends(get_current_user),
    service: CompaniesService = Depends(get_companies_service),
) -> dict:
    return as_page(service.list(user, q=q, active=active, limit=limit, cursor=cursor))


@router.post("", response_model=Company, status_code=status.HTTP_201_CREATED)
def create_company(
    payload: CompanyCreate,
    user: Principal = Depends(require_admin),
    service: CompaniesService = Depends(get_companies_service),
) -> dict:
    return service.create(user, payload)


@router.get("/{company_id}", response_model=Company)
def get_company(
    company_id: str,
    user: Principal = Depends(get_current_user),
    service: CompaniesService = Depends(get_companies_service),
) -> dict:
    return service.get(user, company_id)


@router.patch("/{company_id}", response_model=Company)
def update_company(
    company_id: str,
    payload: CompanyUpdate,
    user: Principal = Depends(require_admin),
    service: CompaniesService = Depends(get_companies_service),
) -> dict:
    return service.update(user, company_id, payload)


@router.delete("/{company_id}", response_model=Company)
def deactivate_company(
    company_id: str,
    user: Principal = Depends(require_admin),
    service: CompaniesService = Depends(get_companies_service),
) -> dict:
    return service.deactivate(user, company_id)
