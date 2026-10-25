"""Placement drives and the eligibility engine (FR-23 to FR-28)."""

from __future__ import annotations

from datetime import date
from typing import Any

from app.core.config import settings
from app.core.errors import BadRequest, Forbidden, NotFound
from app.core.pagination import Page, paginate_items
from app.core.scoping import ensure_any_college, ensure_college, is_super_admin, scoped_college_ids
from app.core.security import Principal
from app.models.drive import DriveCreate, DriveUpdate
from app.models.enums import DriveStatus, NotificationType, Role
from app.repositories import Repos
from app.services.audit import AuditService
from app.services.eligibility import evaluate_eligibility
from app.services.metrics import utcnow
from app.services.notify import NotificationService


class DrivesService:
    def __init__(
        self,
        repos: Repos,
        *,
        audit: AuditService | None = None,
        notifications: NotificationService | None = None,
    ) -> None:
        self.repos = repos
        self.audit = audit or AuditService(repos)
        self.notifications = notifications or NotificationService(repos)

    # -- reads --------------------------------------------------------------
    def list(
        self,
        actor: Principal,
        *,
        status: str | None = None,
        college_id: str | None = None,
        q: str | None = None,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> Page:
        if actor.role == Role.STUDENT:
            return self._list_for_student(actor, limit=limit, cursor=cursor)

        docs = self.repos.drives.all(cap=5000)
        if college_id:
            ensure_college(actor, college_id)
            docs = [
                d
                for d in docs
                if not d.get("collegeIds") or college_id in (d.get("collegeIds") or [])
            ]
        elif not is_super_admin(actor):
            allowed = set(actor.college_ids)
            docs = [
                d
                for d in docs
                if not d.get("collegeIds") or allowed.intersection(d.get("collegeIds") or [])
            ]
        if status:
            docs = [d for d in docs if d.get("status") == status]
        if q:
            needle = q.lower()
            docs = [
                d
                for d in docs
                if needle in (d.get("role") or "").lower()
                or needle in (d.get("companyName") or "").lower()
            ]

        docs.sort(key=lambda d: (d.get("driveDate") or "", d["id"]), reverse=True)
        page = paginate_items(docs, order_by="driveDate", limit=limit, cursor=cursor)
        page.items = [self._decorate(d) for d in page.items]
        return page

    def _list_for_student(
        self, actor: Principal, *, limit: int | None, cursor: str | None
    ) -> Page:
        student = self.repos.students.by_uid(actor.uid)
        if student is None:
            return Page(items=[], next_cursor=None)

        docs = [
            drive
            for drive in self.repos.drives.all(cap=5000)
            if drive.get("status") != DriveStatus.DRAFT.value
            and drive.get("status") != DriveStatus.CANCELLED.value
            and (
                not drive.get("collegeIds")
                or student.get("collegeId") in (drive.get("collegeIds") or [])
            )
        ]
        docs.sort(key=lambda d: (d.get("driveDate") or "", d["id"]))
        page = paginate_items(docs, order_by="driveDate", descending=False, limit=limit, cursor=cursor)

        items = []
        for drive in page.items:
            application = self.repos.applications.for_drive_student(drive["id"], student["id"])
            decorated = dict(drive)
            decorated["eligibilityResult"] = evaluate_eligibility(
                drive,
                student,
                applied=application is not None,
            )
            decorated["application"] = application
            items.append(decorated)
        page.items = items
        return page

    def get(self, actor: Principal, drive_id: str) -> dict[str, Any]:
        drive = self._require(drive_id)
        if actor.role == Role.STUDENT:
            student = self.repos.students.by_uid(actor.uid)
            if student is None:
                raise Forbidden("No student profile linked to this account", code="student_forbidden")
            if drive.get("status") in {DriveStatus.DRAFT.value, DriveStatus.CANCELLED.value}:
                raise NotFound(f"Drive {drive_id} not found", code="drive_not_found")
            if drive.get("collegeIds") and student.get("collegeId") not in drive["collegeIds"]:
                raise Forbidden("This drive is not open to your college", code="college_scope_violation")
            application = self.repos.applications.for_drive_student(drive_id, student["id"])
            decorated = dict(drive)
            decorated["eligibilityResult"] = evaluate_eligibility(
                drive, student, applied=application is not None
            )
            decorated["application"] = application
            return decorated

        self._ensure_staff_read(actor, drive)
        return self._decorate(drive)

    def eligible_students(
        self,
        actor: Principal,
        drive_id: str,
        *,
        only_eligible: bool = True,
        limit: int = 100,
    ) -> dict[str, Any]:
        drive = self._require(drive_id)
        self._ensure_staff_read(actor, drive)

        students = self._students_for_drive(actor, drive)
        applied = {
            app["studentId"] for app in self.repos.applications.for_drive(drive_id, limit=5000)
        }
        results = [
            evaluate_eligibility(
                drive, student, applied=student["id"] in applied
            )
            for student in students
        ]
        eligible = [r for r in results if r["eligible"]]
        if only_eligible:
            results = eligible
        results.sort(key=lambda r: r["readinessScore"], reverse=True)
        cap = max(1, min(limit, 1000))
        return {
            "items": results[:cap],
            "total": len(students),
            "eligible": len(eligible),
        }

    # -- writes -------------------------------------------------------------
    def create(self, actor: Principal, payload: DriveCreate) -> dict[str, Any]:
        if not actor.is_admin:
            raise Forbidden("Only admins can create drives", code="role_forbidden")
        company = self.repos.companies.get(payload.company_id)
        if company is None:
            raise NotFound(f"Company {payload.company_id} not found", code="company_not_found")

        self._validate_dates(payload.deadline, payload.drive_date)
        self._validate_rounds([r.model_dump(by_alias=True) for r in payload.rounds])
        college_ids = self._resolve_colleges(actor, payload.college_ids, payload.eligibility.batch_ids)
        self._validate_batches(college_ids, payload.eligibility.batch_ids)

        now = utcnow()
        doc = {
            **payload.model_dump(by_alias=True),
            "collegeIds": college_ids,
            "companyName": company.get("name"),
            "createdBy": actor.uid,
            "createdAt": now,
            "updatedAt": now,
        }
        drive = self.repos.drives.create(doc)
        self.audit.record(
            actor,
            "drive.create",
            "drive",
            drive["id"],
            after={"role": payload.role, "company": company.get("name")},
        )
        if drive.get("status") == DriveStatus.OPEN.value:
            self._announce_drive(drive, actor)
        return self._decorate(drive)

    def update(self, actor: Principal, drive_id: str, payload: DriveUpdate) -> dict[str, Any]:
        if not actor.is_admin:
            raise Forbidden("Only admins can update drives", code="role_forbidden")
        drive = self._require(drive_id)
        self._ensure_staff_read(actor, drive)

        patch = payload.model_dump(exclude_unset=True, by_alias=True)
        if not patch:
            return self._decorate(drive)

        if "collegeIds" in patch and patch["collegeIds"] is not None:
            patch["collegeIds"] = self._resolve_colleges(
                actor,
                patch["collegeIds"],
                (patch.get("eligibility") or drive.get("eligibility") or {}).get("batchIds") or [],
            )
        if "rounds" in patch and patch["rounds"] is not None:
            self._validate_rounds(patch["rounds"])
        eligibility = patch.get("eligibility") or drive.get("eligibility") or {}
        self._validate_batches(
            patch.get("collegeIds", drive.get("collegeIds") or []),
            eligibility.get("batchIds") or [],
        )
        self._validate_dates(
            patch.get("deadline", drive.get("deadline")),
            patch.get("driveDate", drive.get("driveDate")),
        )

        previous_status = drive.get("status")
        patch["updatedAt"] = utcnow()
        updated = self.repos.drives.update(drive_id, patch)
        if previous_status != DriveStatus.OPEN.value and updated.get("status") == DriveStatus.OPEN.value:
            self._announce_drive(updated, actor)

        self.audit.record(
            actor,
            "drive.update",
            "drive",
            drive_id,
            before={key: drive.get(key) for key in patch if key != "updatedAt"},
            after=patch,
        )
        return self._decorate(updated)

    # -- helpers ------------------------------------------------------------
    def _require(self, drive_id: str) -> dict[str, Any]:
        drive = self.repos.drives.get(drive_id)
        if drive is None:
            raise NotFound(f"Drive {drive_id} not found", code="drive_not_found")
        return drive

    def _ensure_staff_read(self, actor: Principal, drive: dict[str, Any]) -> None:
        if actor.role == Role.STUDENT:
            raise Forbidden("Students cannot access this endpoint", code="role_forbidden")
        drive_colleges = drive.get("collegeIds") or []
        if drive_colleges:
            ensure_any_college(actor, drive_colleges)

    def _decorate(self, drive: dict[str, Any]) -> dict[str, Any]:
        doc = dict(drive)
        applications = self.repos.applications.for_drive(drive["id"], limit=5000)
        stats = {
            "eligible": 0,
            "applied": 0,
            "shortlisted": 0,
            "selected": 0,
            "rejected": 0,
            "withdrawn": 0,
        }
        for application in applications:
            status_value = application.get("status")
            stats["applied"] += 1
            if status_value in stats:
                stats[status_value] += 1
        doc["stats"] = stats
        return doc

    def _resolve_colleges(
        self, actor: Principal, college_ids: list[str], batch_ids: list[str]
    ) -> list[str]:
        if college_ids:
            for college_id in college_ids:
                ensure_college(actor, college_id)
                if self.repos.colleges.get(college_id) is None:
                    raise BadRequest(f"College {college_id} not found", code="college_not_found")
            return list(dict.fromkeys(college_ids))
        if is_super_admin(actor):
            return []
        if not actor.college_ids:
            raise BadRequest("No college scope available for this drive", code="college_required")
        return list(actor.college_ids)

    def _validate_batches(self, college_ids: list[str], batch_ids: list[str]) -> None:
        for batch_id in batch_ids or []:
            batch = self.repos.batches.get(batch_id)
            if batch is None:
                raise BadRequest(f"Batch {batch_id} not found", code="batch_not_found")
            if college_ids and batch.get("collegeId") not in college_ids:
                raise BadRequest(
                    f"Batch {batch_id} is outside the drive's colleges", code="batch_college_mismatch"
                )

    def _validate_dates(self, deadline: str, drive_date: str) -> None:
        try:
            deadline_date = date.fromisoformat(deadline)
            drive_day = date.fromisoformat(drive_date)
        except (ValueError, TypeError) as exc:
            raise BadRequest("Drive dates must be ISO formatted (YYYY-MM-DD)") from exc
        if deadline_date > drive_day:
            raise BadRequest("Application deadline cannot be after the drive date", code="invalid_date_range")

    def _validate_rounds(self, rounds: list[dict[str, Any]]) -> None:
        names = [r.get("name") for r in rounds if r.get("name")]
        if len(names) != len(set(names)):
            raise BadRequest("Round names must be unique", code="duplicate_round")

    def _students_for_drive(self, actor: Principal, drive: dict[str, Any]) -> list[dict[str, Any]]:
        college_ids = drive.get("collegeIds") or []
        if not college_ids:
            allowed = scoped_college_ids(actor)
            if allowed is None:
                return self.repos.students.all(cap=20000)
            students: list[dict[str, Any]] = []
            for college_id in allowed:
                students.extend(self.repos.students.for_college(college_id, limit=20000))
            return students
        students = []
        for college_id in college_ids:
            ensure_college(actor, college_id)
            students.extend(self.repos.students.for_college(college_id, limit=20000))
        return students

    def _announce_drive(self, drive: dict[str, Any], actor: Principal) -> None:
        students = self._students_for_drive(actor, drive)
        eligible_uids = [
            student["uid"]
            for student in students
            if evaluate_eligibility(drive, student)["eligible"]
        ]
        if not eligible_uids:
            return
        self.notifications.notify(
            eligible_uids,
            notification_type=NotificationType.DRIVE,
            title=f"New drive: {drive.get('companyName')} — {drive.get('role')}",
            body=(
                f"CTC {drive.get('ctc')} LPA · Apply by {drive.get('deadline')}. "
                f"Location: {drive.get('location') or 'TBD'}."
            ),
            link=f"/drives/{drive['id']}",
            email=settings.email_enabled,
        )
