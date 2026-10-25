"""College / batch / student scoping helpers.

FR-6: non-super admins and trainers only see colleges in their ``collegeIds``
claim. Students only see themselves. Every service calls these before touching
a document.
"""

from __future__ import annotations

from typing import Any, Iterable

from app.core.errors import Forbidden, NotFound
from app.core.security import Principal
from app.models.enums import Role


def is_super_admin(user: Principal) -> bool:
    return bool(user.super_admin or "*" in (user.college_ids or []))


def scoped_college_ids(user: Principal) -> list[str] | None:
    """``None`` means every college (super admin)."""
    if is_super_admin(user):
        return None
    return list(user.college_ids or [])


def ensure_college(user: Principal, college_id: str | None) -> None:
    if not college_id:
        raise Forbidden("Missing college scope", code="college_scope_violation")
    allowed = scoped_college_ids(user)
    if allowed is not None and college_id not in allowed:
        raise Forbidden(
            "You do not have access to this college", code="college_scope_violation"
        )


def ensure_any_college(user: Principal, college_ids: Iterable[str]) -> None:
    allowed = scoped_college_ids(user)
    if allowed is None:
        return
    if not set(college_ids) & set(allowed):
        raise Forbidden("You do not have access to these colleges", code="college_scope_violation")


def ensure_batch_access(user: Principal, batch: dict[str, Any], *, write: bool = False) -> None:
    """Admins need college scope; trainers must be assigned to the batch."""
    if user.role == Role.ADMIN:
        ensure_college(user, batch.get("collegeId"))
        return
    if user.role == Role.TRAINER:
        ensure_college(user, batch.get("collegeId"))
        if user.uid not in (batch.get("trainerIds") or []):
            raise Forbidden("You are not assigned to this batch", code="batch_forbidden")
        return
    raise Forbidden("Students cannot access batch administration", code="role_forbidden")


def ensure_student_access(
    user: Principal, student: dict[str, Any], *, batch: dict[str, Any] | None = None
) -> None:
    """Ownership check: student → self, trainer → assigned batch, admin → college."""
    if user.role == Role.STUDENT:
        if student.get("uid") != user.uid:
            raise Forbidden("You can only access your own record", code="student_forbidden")
        return
    if user.role == Role.ADMIN:
        ensure_college(user, student.get("collegeId"))
        return
    if user.role == Role.TRAINER:
        ensure_college(user, student.get("collegeId"))
        if batch is None:
            raise Forbidden("Batch context is required", code="batch_forbidden")
        if user.uid not in (batch.get("trainerIds") or []):
            raise Forbidden("You are not assigned to this student's batch", code="batch_forbidden")
        return
    raise Forbidden("Unsupported role", code="role_forbidden")


def require_student_doc(student: dict[str, Any] | None, student_id: str) -> dict[str, Any]:
    if student is None:
        raise NotFound(f"Student {student_id} not found", code="student_not_found")
    return student
