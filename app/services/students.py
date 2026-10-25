"""Student profiles, search, CSV import and resumes (FR-10 to FR-14)."""

from __future__ import annotations

from typing import Any

from app.core.errors import BadRequest, Forbidden, NotFound
from app.core.pagination import Page, paginate_items
from app.core.scoping import ensure_college, ensure_student_access, scoped_college_ids
from app.core.security import Principal
from app.models.enums import Role
from app.models.student import StudentUpdate
from app.models.user import BulkImportResult
from app.repositories import Repos
from app.services.audit import AuditService
from app.services.files import FileService
from app.services.metrics import compute_profile_score, utcnow
from app.services.users import UsersService

PERSONAL_FIELDS = {"name", "phone", "skills", "projects", "certifications", "links"}
ACADEMIC_FIELDS = {"rollNo", "degree", "branch", "gradYear", "cgpa"}
ADMIN_FIELDS = {"placementStatus", "placementLocked"}


class StudentsService:
    def __init__(
        self,
        repos: Repos,
        *,
        files: FileService | None = None,
        audit: AuditService | None = None,
        users: UsersService | None = None,
    ) -> None:
        self.repos = repos
        self.files = files or FileService()
        self.audit = audit or AuditService(repos)
        self.users = users or UsersService(repos)

    # -- reads --------------------------------------------------------------
    def list(
        self,
        actor: Principal,
        *,
        college_id: str | None = None,
        batch_id: str | None = None,
        skills: list[str] | None = None,
        min_cgpa: float | None = None,
        max_cgpa: float | None = None,
        placement_status: str | None = None,
        at_risk: bool | None = None,
        q: str | None = None,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> Page:
        if actor.role == Role.STUDENT:
            student = self.repos.students.by_uid(actor.uid)
            return Page(items=[student] if student else [], next_cursor=None)

        filters: list[tuple[str, str, Any]] = []
        if actor.role == Role.TRAINER:
            batches = self.repos.batches.for_trainer(actor.uid, actor.college_ids)
            batch_ids = [b["id"] for b in batches]
            if batch_id:
                if batch_id not in batch_ids:
                    raise Forbidden("You are not assigned to this batch", code="batch_forbidden")
                batch_ids = [batch_id]
            if not batch_ids:
                return Page(items=[], next_cursor=None)
            filters.append(("batchId", "in", batch_ids))
        elif batch_id:
            filters.append(("batchId", "==", batch_id))

        if college_id:
            ensure_college(actor, college_id)
            filters.append(("collegeId", "==", college_id))
        elif actor.role == Role.ADMIN:
            allowed = scoped_college_ids(actor)
            if allowed is not None:
                if not allowed:
                    return Page(items=[], next_cursor=None)
                filters.append(("collegeId", "in", allowed))
        else:
            filters.append(("collegeId", "in", actor.college_ids))

        if skills:
            filters.append(("skills", "array_contains_any", skills))
        if min_cgpa is not None:
            filters.append(("cgpa", ">=", min_cgpa))
        if max_cgpa is not None:
            filters.append(("cgpa", "<=", max_cgpa))
        if placement_status:
            filters.append(("placementStatus", "==", placement_status))
        if at_risk is not None:
            filters.append(("atRisk", "==", at_risk))

        if q:
            # Free-text search spans name, email and roll number. Firestore has no
            # cheap OR/contains query, so filter the college-scoped set in memory.
            docs = self.repos.students.all(filters, cap=20000)
            needle = q.lower().strip()
            docs = [
                d
                for d in docs
                if needle in (d.get("name") or "").lower()
                or needle in (d.get("email") or "").lower()
                or needle in (d.get("rollNo") or "").lower()
            ]
            return paginate_items(docs, order_by="name", limit=limit, cursor=cursor)

        # Multi-filter result sets are easier (and cheaper) in memory than maintaining
        # a composite index for every filter combination.
        if (
            actor.role == Role.TRAINER
            or batch_id
            or skills
            or min_cgpa is not None
            or max_cgpa is not None
            or placement_status
            or at_risk is not None
        ):
            docs = self.repos.students.all(filters, cap=20000)
            return paginate_items(docs, order_by="createdAt", descending=True, limit=limit, cursor=cursor)

        return self.repos.students.list(
            filters,
            order_by="createdAt",
            descending=True,
            limit=limit,
            cursor=cursor,
        )

    def get(self, actor: Principal, student_id: str) -> dict[str, Any]:
        student = self._require(student_id)
        self._ensure_view(actor, student)
        return student

    def me(self, actor: Principal) -> dict[str, Any]:
        student = self.repos.students.by_uid(actor.uid)
        if student is None:
            raise NotFound("No student profile is linked to this account", code="student_not_found")
        return student

    # -- writes -------------------------------------------------------------
    def update(self, actor: Principal, student_id: str, payload: StudentUpdate) -> dict[str, Any]:
        student = self._require(student_id)
        self._ensure_view(actor, student)

        patch = payload.model_dump(exclude_unset=True, by_alias=True)
        if not patch:
            return student

        allowed: set[str] = set()
        if actor.role == Role.ADMIN:
            allowed = PERSONAL_FIELDS | ACADEMIC_FIELDS | ADMIN_FIELDS
        elif actor.role == Role.TRAINER:
            allowed = ACADEMIC_FIELDS
        else:
            allowed = PERSONAL_FIELDS

        disallowed = set(patch) - allowed
        if disallowed:
            raise Forbidden(
                f"You cannot edit these fields: {', '.join(sorted(disallowed))}",
                code="field_forbidden",
                details={"fields": sorted(disallowed)},
            )

        if "name" in patch and not patch["name"]:
            raise BadRequest("Name cannot be empty")

        before = {key: student.get(key) for key in patch}
        patch["updatedAt"] = utcnow()
        merged = {**student, **patch}
        patch["profileScore"] = compute_profile_score(merged)
        updated = self.repos.students.update(student_id, patch)

        if "name" in patch:
            self.repos.users.update(updated["uid"], {"name": patch["name"], "updatedAt": utcnow()})

        self.audit.record(
            actor,
            "student.update",
            "student",
            student_id,
            before=before,
            after=patch,
        )
        return updated

    async def upload_resume(self, actor: Principal, student_id: str, upload: Any) -> dict[str, Any]:
        student = self._require(student_id)
        if not (actor.is_admin or student.get("uid") == actor.uid):
            raise Forbidden("You can only upload your own resume", code="student_forbidden")

        path = await self.files.upload_resume(
            college_id=student["collegeId"], student_id=student_id, upload=upload
        )
        merged = {**student, "resumePath": path}
        updated = self.repos.students.update(
            student_id,
            {
                "resumePath": path,
                "profileScore": compute_profile_score(merged),
                "updatedAt": utcnow(),
            },
        )
        self.audit.record(actor, "student.resume_upload", "student", student_id)
        return {
            "resumePath": path,
            "resumeUrl": self.files.signed_url(path),
            "profileScore": updated.get("profileScore", 0),
        }

    def resume_url(self, actor: Principal, student_id: str) -> dict[str, Any]:
        student = self._require(student_id)
        self._ensure_view(actor, student)
        if not student.get("resumePath"):
            raise NotFound("No resume on file", code="resume_not_found")
        return {
            "resumePath": student["resumePath"],
            "resumeUrl": self.files.signed_url(student["resumePath"]),
            "expiresIn": 900,
        }

    def import_students(self, actor: Principal, data: bytes, *, send_setup_emails: bool = False) -> BulkImportResult:
        if not actor.is_admin:
            raise Forbidden("Only admins can import students", code="role_forbidden")
        return self.users.bulk_create_bytes(
            actor,
            data,
            send_setup_emails=send_setup_emails,
            forced_role=Role.STUDENT,
            required={"name", "email", "collegeid"},
        )

    # -- helpers ------------------------------------------------------------
    def _require(self, student_id: str) -> dict[str, Any]:
        student = self.repos.students.get(student_id)
        if student is None:
            raise NotFound(f"Student {student_id} not found", code="student_not_found")
        return student

    def _ensure_view(self, actor: Principal, student: dict[str, Any]) -> None:
        batch = self.repos.batches.get(student["batchId"]) if student.get("batchId") else None
        ensure_student_access(actor, student, batch=batch)
