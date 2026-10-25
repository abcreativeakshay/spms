"""User administration: single + bulk onboarding, roles, disable (FR-4, FR-5)."""

from __future__ import annotations

from typing import Any

from app.core.errors import BadRequest, Conflict, Forbidden
from app.core.firebase import AuthProvider, get_auth_provider
from app.core.pagination import Page
from app.core.scoping import ensure_college, is_super_admin, scoped_college_ids
from app.core.security import Principal
from app.models.enums import Role
from app.models.user import BulkImportResult, BulkRowError, UserCreate, UserUpdate
from app.repositories import Repos
from app.services.audit import AuditService
from app.services.csv_utils import parse_csv, parse_float, parse_int, split_list
from app.services.metrics import compute_profile_score, utcnow
from app.services.notify import NotificationService

_MANAGEABLE_BY_ADMIN = {Role.TRAINER, Role.STUDENT}


class UsersService:
    def __init__(
        self,
        repos: Repos,
        *,
        auth: AuthProvider | None = None,
        audit: AuditService | None = None,
        notifications: NotificationService | None = None,
    ) -> None:
        self.repos = repos
        self.auth = auth or get_auth_provider()
        self.audit = audit or AuditService(repos)
        self.notifications = notifications or NotificationService(repos)

    # -- reads --------------------------------------------------------------
    def list(
        self,
        actor: Principal,
        *,
        role: str | None = None,
        college_id: str | None = None,
        active: bool | None = None,
        q: str | None = None,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> Page:
        filters: list[tuple[str, str, Any]] = []
        if role:
            filters.append(("role", "==", role))
        if active is not None:
            filters.append(("active", "==", active))
        if college_id:
            ensure_college(actor, college_id)
            filters.append(("collegeIds", "array_contains", college_id))
        else:
            allowed = scoped_college_ids(actor)
            if allowed is not None:
                if not allowed:
                    return Page(items=[], next_cursor=None)
                filters.append(("collegeIds", "array_contains_any", allowed))
        if q:
            filters.append(("name", ">=", q))
            filters.append(("name", "<=", q + "\uf8ff"))
        page = self.repos.users.list(
            filters,
            order_by="name" if q else "createdAt",
            descending=not q,
            limit=limit,
            cursor=cursor,
        )
        return page

    def get(self, actor: Principal, uid: str) -> dict[str, Any]:
        user = self.repos.users.require(uid, "User")
        self._ensure_manageable(actor, user)
        return user

    # -- create -------------------------------------------------------------
    def create(self, actor: Principal, payload: UserCreate) -> tuple[dict[str, Any], str | None]:
        self._ensure_can_assign_role(actor, payload.role, payload.college_ids)
        college_ids = self._normalize_colleges(actor, payload.role, payload.college_ids, payload.college_id)
        email = payload.email.lower()
        if self.repos.users.by_email(email):
            raise Conflict(f"A user with email {email} already exists", code="email_taken")

        claims = {
            "role": payload.role.value,
            "collegeIds": college_ids,
            "superAdmin": bool(payload.super_admin),
        }
        uid = self.auth.create_user(
            email=email,
            password=payload.password,
            display_name=payload.name,
            claims=claims,
        )
        now = utcnow()
        user_doc = {
            "uid": uid,
            "role": payload.role.value,
            "name": payload.name,
            "email": email,
            "collegeIds": college_ids,
            "phone": payload.phone,
            "superAdmin": bool(payload.super_admin),
            "active": True,
            "createdAt": now,
            "updatedAt": now,
        }
        self.repos.users.create(user_doc, doc_id=uid)

        if payload.role == Role.STUDENT:
            self._create_student_profile(uid, payload, college_ids[0])

        self.audit.record(actor, "user.create", "user", uid, after={"role": payload.role.value, "email": email})

        setup_link = None
        if payload.send_setup_email and not payload.password:
            setup_link = self.auth.password_reset_link(email)
            if setup_link:
                self.notifications.queue_email(
                    uid,
                    "Set up your SPMS password",
                    f"Welcome to SPMS. Set your password here: {setup_link}",
                )
        return {"id": uid, **user_doc}, setup_link

    def bulk_create_bytes(
        self,
        actor: Principal,
        data: bytes,
        *,
        send_setup_emails: bool = False,
        forced_role: Role | None = None,
        required: set[str] | None = None,
    ) -> BulkImportResult:
        required_columns = required or (
            {"name", "email", "collegeId"}
            if forced_role == Role.STUDENT
            else {"name", "email", "role"}
        )
        rows = parse_csv(data, required=required_columns, max_rows=500)
        result = BulkImportResult()
        seen: set[str] = set()

        for index, row in enumerate(rows, start=2):
            email = (row.get("email") or "").lower()
            try:
                if not email or "@" not in email:
                    raise ValueError("Valid email is required")
                if email in seen:
                    raise ValueError("Duplicate email in file")
                seen.add(email)
                if self.repos.users.by_email(email):
                    raise ValueError("Email already exists")

                college_ids = split_list(row.get("collegeids")) or split_list(row.get("collegeid"))
                payload = UserCreate(
                    name=row.get("name") or "",
                    email=email,
                    role=forced_role or Role(row.get("role") or ""),
                    college_ids=college_ids,
                    phone=row.get("phone") or None,
                    college_id=row.get("collegeid") or (college_ids[0] if college_ids else None),
                    batch_id=row.get("batchid") or None,
                    roll_no=row.get("rollno") or None,
                    degree=row.get("degree") or None,
                    branch=row.get("branch") or None,
                    grad_year=parse_int(row.get("gradyear"), "gradYear"),
                    cgpa=parse_float(row.get("cgpa"), "cgpa"),
                    skills=split_list(row.get("skills")),
                    send_setup_email=send_setup_emails,
                )
                if forced_role == Role.STUDENT and len(college_ids) != 1:
                    raise ValueError("Students must have exactly one collegeId")
                user, link = self.create(actor, payload)
                result.created += 1
                if link:
                    result.setup_links[user["email"]] = link
            except Exception as exc:  # noqa: BLE001 - per-row error report
                result.failed += 1
                result.errors.append(
                    BulkRowError(row=index, email=email or None, message=_error_message(exc))
                )
        return result

    # -- update / disable ---------------------------------------------------
    def update(self, actor: Principal, uid: str, payload: UserUpdate) -> dict[str, Any]:
        user = self.repos.users.require(uid, "User")
        self._ensure_manageable(actor, user)
        if user["id"] == actor.uid and payload.role and payload.role != user["role"]:
            raise BadRequest("You cannot change your own role", code="self_role_change")

        patch: dict[str, Any] = {}
        claims_changed = False

        if payload.name is not None:
            patch["name"] = payload.name
        if payload.phone is not None:
            patch["phone"] = payload.phone

        if payload.role is not None and payload.role.value != user["role"]:
            if Role.STUDENT in {payload.role, Role(user["role"])}:
                raise BadRequest(
                    "Accounts cannot be converted to or from the student role; create a new account",
                    code="role_conversion_unsupported",
                )
            self._ensure_can_assign_role(actor, payload.role, user.get("collegeIds", []))
            patch["role"] = payload.role.value
            claims_changed = True

        if payload.college_ids is not None:
            college_ids = self._normalize_colleges(actor, Role(user["role"]), payload.college_ids)
            patch["collegeIds"] = college_ids
            claims_changed = True

        if payload.super_admin is not None:
            if not is_super_admin(actor) and actor.uid != uid:
                raise Forbidden("Only a super admin can change super admin status")
            patch["superAdmin"] = payload.super_admin
            claims_changed = True

        if payload.active is not None:
            patch["active"] = payload.active

        if not patch:
            return user

        patch["updatedAt"] = utcnow()
        updated = self.repos.users.update(uid, patch)

        if claims_changed:
            self.auth.set_claims(
                uid,
                {
                    "role": updated["role"],
                    "collegeIds": updated.get("collegeIds", []),
                    "superAdmin": bool(updated.get("superAdmin")),
                },
            )
            # Stale custom claims are a known risk (PRD §12): force re-login.
            self.auth.revoke_tokens(uid)

        if updated["role"] == Role.STUDENT.value and "collegeIds" in patch:
            student = self.repos.students.by_uid(uid)
            if student:
                self.repos.students.update(
                    student["id"], {"collegeId": updated["collegeIds"][0], "updatedAt": utcnow()}
                )

        self.audit.record(
            actor,
            "user.update",
            "user",
            uid,
            before=_safe_user(user),
            after=_safe_user(updated),
        )
        return updated

    def set_active(self, actor: Principal, uid: str, active: bool) -> dict[str, Any]:
        user = self.repos.users.require(uid, "User")
        self._ensure_manageable(actor, user)
        if uid == actor.uid and not active:
            raise BadRequest("You cannot disable your own account", code="self_disable")
        updated = self.repos.users.update(uid, {"active": active, "updatedAt": utcnow()})
        if not active:
            self.auth.revoke_tokens(uid)
        self.audit.record(
            actor,
            "user.enable" if active else "user.disable",
            "user",
            uid,
            before={"active": user.get("active", True)},
            after={"active": active},
        )
        return updated

    # -- helpers ------------------------------------------------------------
    def _create_student_profile(self, uid: str, payload: UserCreate, college_id: str) -> dict[str, Any]:
        college = self.repos.colleges.get(college_id)
        if college is None:
            raise BadRequest(f"College {college_id} not found", code="college_not_found")

        batch = None
        if payload.batch_id:
            batch = self.repos.batches.get(payload.batch_id)
            if batch is None:
                raise BadRequest(f"Batch {payload.batch_id} not found", code="batch_not_found")
            if batch.get("collegeId") != college_id:
                raise BadRequest("Batch does not belong to the selected college", code="batch_college_mismatch")

        now = utcnow()
        doc = {
            "uid": uid,
            "name": payload.name,
            "email": payload.email.lower(),
            "phone": payload.phone,
            "collegeId": college_id,
            "collegeName": college.get("name"),
            "batchId": payload.batch_id,
            "batchName": (batch or {}).get("name"),
            "rollNo": payload.roll_no,
            "degree": payload.degree,
            "branch": payload.branch,
            "gradYear": payload.grad_year,
            "cgpa": payload.cgpa,
            "skills": payload.skills,
            "projects": [],
            "certifications": [],
            "links": None,
            "resumePath": None,
            "profileScore": 0,
            "placementStatus": "unplaced",
            "placementLocked": False,
            "placedCompany": None,
            "placedCtc": None,
            "attendancePct": 0.0,
            "assessmentAvg": 0.0,
            "interviewAvg": 0.0,
            "readinessScore": 0.0,
            "atRisk": False,
            "createdAt": now,
            "updatedAt": now,
        }
        doc["profileScore"] = compute_profile_score(doc)
        created = self.repos.students.create(doc)
        if payload.batch_id and batch:
            self.repos.batches.update(
                payload.batch_id,
                {"studentCount": self.repos.students.count([("batchId", "==", payload.batch_id)])},
            )
        return created

    def _normalize_colleges(
        self,
        actor: Principal,
        role: Role,
        college_ids: list[str],
        primary_college_id: str | None = None,
    ) -> list[str]:
        if role == Role.STUDENT:
            chosen = [primary_college_id] if primary_college_id else list(college_ids)
            if len(chosen) != 1:
                raise BadRequest("Students must belong to exactly one college", code="college_required")
            ensure_college(actor, chosen[0])
            return chosen

        ids = list(dict.fromkeys([*(college_ids or []), *([primary_college_id] if primary_college_id else [])]))
        if not ids:
            raise BadRequest("At least one college is required", code="college_required")
        for college_id in ids:
            ensure_college(actor, college_id)
            if self.repos.colleges.get(college_id) is None:
                raise BadRequest(f"College {college_id} not found", code="college_not_found")
        return ids

    def _ensure_can_assign_role(self, actor: Principal, role: Role, college_ids: list[str]) -> None:
        if not actor.is_admin:
            raise Forbidden("Only admins can manage users", code="role_forbidden")
        if role in _MANAGEABLE_BY_ADMIN:
            return
        if role == Role.ADMIN and is_super_admin(actor):
            return
        raise Forbidden("Only a super admin can create other admins", code="role_forbidden")

    def _ensure_manageable(self, actor: Principal, user: dict[str, Any]) -> None:
        if not actor.is_admin:
            raise Forbidden("Only admins can manage users", code="role_forbidden")
        if user.get("superAdmin") and not is_super_admin(actor) and user["id"] != actor.uid:
            raise Forbidden("Only a super admin can manage another super admin")
        for college_id in user.get("collegeIds", []):
            ensure_college(actor, college_id)


def _error_message(exc: Exception) -> str:
    from app.core.errors import AppError

    if isinstance(exc, AppError):
        return exc.message
    return str(exc) or exc.__class__.__name__


def _safe_user(user: dict[str, Any]) -> dict[str, Any]:
    return {
        "role": user.get("role"),
        "collegeIds": user.get("collegeIds", []),
        "active": user.get("active", True),
        "superAdmin": user.get("superAdmin", False),
        "name": user.get("name"),
        "email": user.get("email"),
    }


def re_or_none(value: str | None) -> str | None:
    return value or None
