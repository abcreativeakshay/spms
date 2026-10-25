"""Company catalogue managed by admins (FR-23)."""

from __future__ import annotations

from typing import Any

from app.core.errors import Forbidden, NotFound
from app.core.pagination import Page
from app.core.security import Principal
from app.models.drive import CompanyCreate, CompanyUpdate
from app.repositories import Repos
from app.services.audit import AuditService
from app.services.metrics import utcnow


class CompaniesService:
    def __init__(self, repos: Repos, audit: AuditService | None = None) -> None:
        self.repos = repos
        self.audit = audit or AuditService(repos)

    def list(
        self,
        actor: Principal,
        *,
        q: str | None = None,
        active: bool | None = None,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> Page:
        filters: list[tuple[str, str, Any]] = []
        if active is not None:
            filters.append(("active", "==", active))
        if q:
            filters.append(("name", ">=", q))
            filters.append(("name", "<=", q + "\uf8ff"))
        page = self.repos.companies.list(
            filters,
            order_by="name" if q else "createdAt",
            descending=not q,
            limit=limit,
            cursor=cursor,
        )
        page.items = [self._decorate(doc) for doc in page.items]
        return page

    def _decorate(self, company: dict[str, Any]) -> dict[str, Any]:
        doc = dict(company)
        doc["driveCount"] = self.repos.drives.count([("companyId", "==", company["id"])])
        return doc

    def get(self, actor: Principal, company_id: str) -> dict[str, Any]:
        company = self.repos.companies.get(company_id)
        if company is None:
            raise NotFound(f"Company {company_id} not found", code="company_not_found")
        return self._decorate(company)

    def create(self, actor: Principal, payload: CompanyCreate) -> dict[str, Any]:
        if not actor.is_admin:
            raise Forbidden("Only admins can manage companies", code="role_forbidden")
        now = utcnow()
        company = self.repos.companies.create(
            {**payload.model_dump(by_alias=True), "createdAt": now, "createdBy": actor.uid, "updatedAt": now}
        )
        self.audit.record(actor, "company.create", "company", company["id"], after={"name": company["name"]})
        return company

    def update(self, actor: Principal, company_id: str, payload: CompanyUpdate) -> dict[str, Any]:
        if not actor.is_admin:
            raise Forbidden("Only admins can manage companies", code="role_forbidden")
        company = self.repos.companies.get(company_id)
        if company is None:
            raise NotFound(f"Company {company_id} not found", code="company_not_found")
        patch = payload.model_dump(exclude_unset=True, by_alias=True)
        if not patch:
            return company
        patch["updatedAt"] = utcnow()
        updated = self.repos.companies.update(company_id, patch)
        if "name" in patch and patch["name"] != company.get("name"):
            for drive in self.repos.drives.all([("companyId", "==", company_id)], cap=5000):
                self.repos.drives.update(drive["id"], {"companyName": patch["name"]})
        self.audit.record(actor, "company.update", "company", company_id, after=patch)
        return updated

    def deactivate(self, actor: Principal, company_id: str) -> dict[str, Any]:
        if not actor.is_admin:
            raise Forbidden("Only admins can manage companies", code="role_forbidden")
        company = self.repos.companies.get(company_id)
        if company is None:
            raise NotFound(f"Company {company_id} not found", code="company_not_found")
        updated = self.repos.companies.update(company_id, {"active": False, "updatedAt": utcnow()})
        self.audit.record(actor, "company.deactivate", "company", company_id)
        return updated
