"""College CRUD with college-level isolation (FR-7)."""

from __future__ import annotations

from typing import Any

from app.core.config import settings
from app.core.errors import Forbidden, NotFound
from app.core.pagination import Page
from app.core.scoping import ensure_college, is_super_admin, scoped_college_ids
from app.core.security import Principal
from app.models.student import CollegeCreate, CollegeUpdate
from app.repositories import Repos
from app.services.audit import AuditService
from app.services.metrics import utcnow


class CollegesService:
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
        from app.core.pagination import paginate_items

        allowed = scoped_college_ids(actor)
        if allowed is not None:
            # A scoped admin has a handful of colleges: reading them by id avoids
            # a documentId "in" query and keeps pagination exact.
            docs = [doc for cid in allowed if (doc := self.repos.colleges.get(cid)) is not None]
            if active is not None:
                docs = [doc for doc in docs if doc.get("active", True) is active]
            if q:
                needle = q.lower()
                docs = [doc for doc in docs if needle in (doc.get("name") or "").lower()]
            return paginate_items(
                docs,
                order_by="name" if q else "createdAt",
                descending=not q,
                limit=limit,
                cursor=cursor,
            )

        filters: list[tuple[str, str, Any]] = []
        if active is not None:
            filters.append(("active", "==", active))
        if q:
            filters.append(("name", ">=", q))
            filters.append(("name", "<=", q + "\uf8ff"))
        return self.repos.colleges.list(
            filters,
            order_by="name" if q else "createdAt",
            descending=not q,
            limit=limit,
            cursor=cursor,
        )

    def get(self, actor: Principal, college_id: str) -> dict[str, Any]:
        college = self.repos.colleges.get(college_id)
        if college is None:
            raise NotFound(f"College {college_id} not found", code="college_not_found")
        ensure_college(actor, college_id)
        college["studentCount"] = self.repos.students.count([("collegeId", "==", college_id)])
        college["batchCount"] = self.repos.batches.count([("collegeId", "==", college_id)])
        return college

    def create(self, actor: Principal, payload: CollegeCreate) -> dict[str, Any]:
        if not is_super_admin(actor):
            raise Forbidden("Only a super admin can create colleges", code="super_admin_required")
        now = utcnow()
        doc = {**payload.model_dump(by_alias=True), "createdAt": now, "createdBy": actor.uid, "updatedAt": now}
        college = self.repos.colleges.create(doc)
        self.audit.record(actor, "college.create", "college", college["id"], after={"name": college["name"]})
        return college

    def update(self, actor: Principal, college_id: str, payload: CollegeUpdate) -> dict[str, Any]:
        college = self.repos.colleges.get(college_id)
        if college is None:
            raise NotFound(f"College {college_id} not found", code="college_not_found")
        ensure_college(actor, college_id)

        patch = payload.model_dump(exclude_unset=True, by_alias=True)
        if not patch:
            return college
        patch["updatedAt"] = utcnow()
        updated = self.repos.colleges.update(college_id, patch)

        if "name" in patch and patch["name"] != college.get("name"):
            self._propagate_rename(college_id, patch["name"])

        self.audit.record(
            actor,
            "college.update",
            "college",
            college_id,
            before={k: college.get(k) for k in patch},
            after=patch,
        )
        return updated

    def deactivate(self, actor: Principal, college_id: str) -> dict[str, Any]:
        college = self.repos.colleges.get(college_id)
        if college is None:
            raise NotFound(f"College {college_id} not found", code="college_not_found")
        ensure_college(actor, college_id)
        updated = self.repos.colleges.update(
            college_id, {"active": False, "updatedAt": utcnow()}
        )
        self.audit.record(actor, "college.deactivate", "college", college_id, after={"active": False})
        return updated

    def _propagate_rename(self, college_id: str, name: str) -> None:
        now = utcnow()
        batches = self.repos.batches.for_college(college_id, limit=1000)
        if batches:
            self.repos.batches.write_batch(
                [("update", batch["id"], {"collegeName": name, "updatedAt": now}) for batch in batches]
            )
        students = self.repos.students.for_college(college_id, limit=20000)
        if students:
            for start in range(0, len(students), 500):
                self.repos.students.write_batch(
                    [
                        ("update", student["id"], {"collegeName": name, "updatedAt": now})
                        for student in students[start : start + 500]
                    ]
                )
