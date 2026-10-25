"""Audit trail (FR-39)."""

from __future__ import annotations

from typing import Any

from app.core.logging import request_id_ctx
from app.core.security import Principal
from app.repositories import Repos
from app.services.metrics import utcnow

_ENTITY_COLLECTION = {
    "student": "students",
    "batch": "batches",
    "college": "colleges",
    "session": "sessions",
    "attendance": "attendance",
    "assessment": "assessments",
    "application": "applications",
    "drive": "drives",
    "feedback": "feedback",
    "user": "users",
}


class AuditService:
    def __init__(self, repos: Repos) -> None:
        self.repos = repos

    def record(
        self,
        actor: Principal | None,
        action: str,
        entity: str,
        entity_id: str,
        *,
        before: dict[str, Any] | None = None,
        after: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        doc = {
            "actorId": actor.uid if actor else "system",
            "actorName": actor.name if actor else "system",
            "action": action,
            "entity": entity,
            "entityId": entity_id,
            "collegeId": self._infer_college(entity, entity_id),
            "before": before,
            "after": after,
            "timestamp": utcnow(),
            "requestId": request_id_ctx.get(),
        }
        return self.repos.audit.create(doc)

    def list_logs(
        self,
        actor: Principal,
        *,
        entity: str | None = None,
        limit: int | None = None,
        cursor: str | None = None,
    ):
        from app.core.scoping import scoped_college_ids

        filters: list[tuple[str, str, Any]] = []
        if entity:
            filters.append(("entity", "==", entity))
        allowed = scoped_college_ids(actor)
        if allowed is not None:
            if not allowed:
                from app.core.pagination import Page

                return Page(items=[], next_cursor=None)
            filters.append(("collegeId", "in", allowed))
        return self.repos.audit.list(
            filters, order_by="timestamp", descending=True, limit=limit, cursor=cursor
        )

    def _infer_college(self, entity: str, entity_id: str) -> str | None:
        if entity == "college":
            return entity_id
        collection = _ENTITY_COLLECTION.get(entity)
        if not collection:
            return None
        doc = self.repos.store.get(collection, entity_id)
        if not doc:
            return None
        if collection == "users":
            colleges = doc.get("collegeIds") or []
            return colleges[0] if colleges else None
        college_id = doc.get("collegeId")
        if college_id:
            return college_id
        # Sessions, attendance and scores denormalize the batch rather than the
        # college, so resolve it through the parent record.
        if doc.get("batchId"):
            batch = self.repos.store.get("batches", doc["batchId"])
            if batch:
                return batch.get("collegeId")
        if doc.get("studentId"):
            student = self.repos.store.get("students", doc["studentId"])
            if student:
                return student.get("collegeId")
        if doc.get("driveId"):
            drive = self.repos.store.get("drives", doc["driveId"])
            if drive and len(drive.get("collegeIds") or []) == 1:
                return drive["collegeIds"][0]
        colleges = doc.get("collegeIds") or []
        return colleges[0] if len(colleges) == 1 else None
