"""Generic repository helpers over ``DocumentStore``.

Services only speak to repositories; routers never touch either.
"""

from __future__ import annotations

from typing import Any, ClassVar, Sequence

from app.core.pagination import Filter, Page, paginate
from app.repositories.store import DocumentStore


class BaseRepository:
    collection: ClassVar[str] = ""

    def __init__(self, store: DocumentStore) -> None:
        self.store = store

    # -- reads --------------------------------------------------------------
    def get(self, doc_id: str) -> dict[str, Any] | None:
        return self.store.get(self.collection, doc_id)

    def require(self, doc_id: str, label: str | None = None) -> dict[str, Any]:
        from app.core.errors import NotFound

        doc = self.get(doc_id)
        if doc is None:
            raise NotFound(f"{label or self.collection[:-1].title()} {doc_id} not found")
        return doc

    def find(
        self,
        filters: Sequence[Filter] = (),
        *,
        limit: int = 100,
        order_by: str = "createdAt",
        descending: bool = True,
    ) -> list[dict[str, Any]]:
        return self.store.query(
            self.collection, list(filters), order_by=order_by, descending=descending, limit=limit
        )

    def find_one(self, **fields: Any) -> dict[str, Any] | None:
        filters = [(field, "==", value) for field, value in fields.items()]
        # Equality lookups do not need an ordering or a composite index.
        docs = self.store.query(self.collection, filters, limit=1)
        return docs[0] if docs else None

    def list(
        self,
        filters: Sequence[Filter] = (),
        *,
        order_by: str = "createdAt",
        descending: bool = True,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> Page:
        return paginate(
            self.store,
            self.collection,
            filters,
            order_by=order_by,
            descending=descending,
            limit=limit,
            cursor=cursor,
        )

    def count(self, filters: Sequence[Filter] = ()) -> int:
        return self.store.count(self.collection, list(filters))

    def all(self, filters: Sequence[Filter] = (), *, cap: int = 5000) -> list[dict[str, Any]]:
        """Bounded scan for aggregation jobs (never exposed as a list endpoint)."""
        return self.store.query(self.collection, list(filters), limit=cap)

    # -- writes -------------------------------------------------------------
    def create(self, data: dict[str, Any], doc_id: str | None = None) -> dict[str, Any]:
        return self.store.set(self.collection, doc_id or self.store.new_id(), data)

    def set(
        self, data: dict[str, Any], doc_id: str | None = None, *, merge: bool = False
    ) -> dict[str, Any]:
        return self.store.set(self.collection, doc_id or self.store.new_id(), data, merge=merge)

    def update(self, doc_id: str, patch: dict[str, Any]) -> dict[str, Any]:
        return self.store.update(self.collection, doc_id, patch)

    def delete(self, doc_id: str) -> None:
        self.store.delete(self.collection, doc_id)

    def write_batch(self, ops: Sequence[tuple[str, str | None, dict[str, Any] | None]]) -> None:
        self.store.write_batch([(op, self.collection, doc_id, data) for op, doc_id, data in ops])


# --------------------------------------------------------------------------- #
# Concrete repositories
# --------------------------------------------------------------------------- #
class UsersRepo(BaseRepository):
    collection = "users"

    def by_email(self, email: str) -> dict[str, Any] | None:
        return self.find_one(email=email.lower())

    def by_role(self, role: str, college_id: str | None = None) -> list[dict[str, Any]]:
        filters: list[Filter] = [("role", "==", role)]
        if college_id:
            filters.append(("collegeIds", "array_contains", college_id))
        return self.all(filters, cap=20000)


class CollegesRepo(BaseRepository):
    collection = "colleges"


class BatchesRepo(BaseRepository):
    collection = "batches"

    def for_college(self, college_id: str, limit: int = 200) -> list[dict[str, Any]]:
        return self.find([("collegeId", "==", college_id)], limit=limit, order_by="startDate")

    def for_trainer(self, trainer_id: str, college_ids: list[str]) -> list[dict[str, Any]]:
        docs = self.find([("trainerIds", "array_contains", trainer_id)], limit=500, order_by="startDate")
        if "*" in college_ids:
            return docs
        return [d for d in docs if d.get("collegeId") in college_ids]

    def for_student(self, student: dict[str, Any]) -> dict[str, Any] | None:
        batch_id = student.get("batchId")
        return self.get(batch_id) if batch_id else None


class StudentsRepo(BaseRepository):
    collection = "students"

    def by_uid(self, uid: str) -> dict[str, Any] | None:
        return self.find_one(uid=uid)

    def for_batch(self, batch_id: str, limit: int = 2000) -> list[dict[str, Any]]:
        return self.find([("batchId", "==", batch_id)], limit=limit, order_by="name", descending=False)

    def for_college(self, college_id: str, limit: int = 5000) -> list[dict[str, Any]]:
        return self.find([("collegeId", "==", college_id)], limit=limit, order_by="name", descending=False)

    def placed(self, college_id: str | None = None) -> list[dict[str, Any]]:
        filters: list[Filter] = [("placementStatus", "==", "placed")]
        if college_id:
            filters.append(("collegeId", "==", college_id))
        return self.all(filters, cap=20000)


class SessionsRepo(BaseRepository):
    collection = "sessions"

    def for_batch(self, batch_id: str, limit: int = 1000) -> list[dict[str, Any]]:
        return self.find([("batchId", "==", batch_id)], limit=limit, order_by="date")


class AttendanceRepo(BaseRepository):
    collection = "attendance"

    def for_session(self, session_id: str) -> list[dict[str, Any]]:
        return self.all([("sessionId", "==", session_id)], cap=2000)

    def for_student(self, student_id: str, limit: int = 5000) -> list[dict[str, Any]]:
        return self.all([("studentId", "==", student_id)], cap=limit)

    def for_batch(self, batch_id: str, limit: int = 50000) -> list[dict[str, Any]]:
        return self.all([("batchId", "==", batch_id)], cap=limit)


class AssessmentsRepo(BaseRepository):
    collection = "assessments"

    def for_batch(self, batch_id: str, limit: int = 500) -> list[dict[str, Any]]:
        return self.find([("batchId", "==", batch_id)], limit=limit, order_by="date")


class ScoresRepo(BaseRepository):
    collection = "scores"

    def for_student(self, student_id: str, limit: int = 2000) -> list[dict[str, Any]]:
        return self.all([("studentId", "==", student_id)], cap=limit)

    def for_assessment(self, assessment_id: str) -> list[dict[str, Any]]:
        return self.all([("assessmentId", "==", assessment_id)], cap=2000)

    def for_batch(self, batch_id: str, limit: int = 50000) -> list[dict[str, Any]]:
        return self.all([("batchId", "==", batch_id)], cap=limit)


class CompaniesRepo(BaseRepository):
    collection = "companies"


class DrivesRepo(BaseRepository):
    collection = "drives"

    def open_drives(self, limit: int = 500) -> list[dict[str, Any]]:
        return self.find([("status", "==", "open")], limit=limit, order_by="driveDate")


class ApplicationsRepo(BaseRepository):
    collection = "applications"

    def for_drive(self, drive_id: str, limit: int = 5000) -> list[dict[str, Any]]:
        return self.all([("driveId", "==", drive_id)], cap=limit)

    def for_student(self, student_id: str, limit: int = 500) -> list[dict[str, Any]]:
        return self.find([("studentId", "==", student_id)], limit=limit, order_by="appliedAt")

    def for_drive_student(self, drive_id: str, student_id: str) -> dict[str, Any] | None:
        return self.find_one(driveId=drive_id, studentId=student_id)


class FeedbackRepo(BaseRepository):
    collection = "feedback"

    def for_student(self, student_id: str, limit: int = 500) -> list[dict[str, Any]]:
        return self.find([("studentId", "==", student_id)], limit=limit, order_by="date")


class NotificationsRepo(BaseRepository):
    collection = "notifications"

    def for_user(self, user_id: str, limit: int = 500) -> list[dict[str, Any]]:
        return self.find([("userId", "==", user_id)], limit=limit, order_by="createdAt")

    def unread_count(self, user_id: str) -> int:
        return self.count([("userId", "==", user_id), ("read", "==", False)])


class AuditRepo(BaseRepository):
    collection = "auditLogs"


class SnapshotsRepo(BaseRepository):
    collection = "analytics_snapshots"

    def for_scope(self, scope: str, scope_id: str) -> dict[str, Any] | None:
        return self.find_one(scope=scope, scopeId=scope_id)


class BatchHistoryRepo(BaseRepository):
    collection = "batchAssignments"
