"""Applications: apply, round results, outcomes, offer letters (FR-25 to FR-28)."""

from __future__ import annotations

from typing import Any

from app.core.errors import BadRequest, Conflict, Forbidden, NotFound
from app.core.pagination import Page, paginate_items
from app.core.scoping import ensure_college, ensure_student_access, scoped_college_ids
from app.core.security import Principal
from app.models.drive import OutcomeUpdate, RoundUpdate
from app.models.enums import (
    ApplicationStatus,
    NotificationType,
    PlacementStatus,
    Role,
    RoundResultStatus,
)
from app.repositories import Repos
from app.services.audit import AuditService
from app.services.eligibility import drive_is_open, evaluate_eligibility
from app.services.files import FileService
from app.services.metrics import MetricsService, utcnow
from app.services.notify import NotificationService


class ApplicationsService:
    def __init__(
        self,
        repos: Repos,
        *,
        audit: AuditService | None = None,
        notifications: NotificationService | None = None,
        metrics: MetricsService | None = None,
        files: FileService | None = None,
    ) -> None:
        self.repos = repos
        self.audit = audit or AuditService(repos)
        self.notifications = notifications or NotificationService(repos)
        self.metrics = metrics or MetricsService(repos)
        self.files = files or FileService()

    # -- student apply ------------------------------------------------------
    def apply(self, actor: Principal, drive_id: str, *, cover_note: str | None = None) -> dict[str, Any]:
        if actor.role != Role.STUDENT:
            raise Forbidden("Only students can apply to drives", code="role_forbidden")
        student = self.repos.students.by_uid(actor.uid)
        if student is None:
            raise Forbidden("No student profile linked to this account", code="student_forbidden")

        drive = self._drive(drive_id)
        if drive.get("collegeIds") and student.get("collegeId") not in drive["collegeIds"]:
            raise Forbidden("This drive is not open to your college", code="college_scope_violation")
        if not drive_is_open(drive, drive.get("deadline")):
            raise Conflict("Applications are closed for this drive", code="drive_closed")
        if self.repos.applications.for_drive_student(drive_id, student["id"]):
            raise Conflict("You have already applied to this drive", code="already_applied")

        eligibility = evaluate_eligibility(drive, student)
        if not eligibility["eligible"]:
            raise Forbidden(
                "You are not eligible for this drive",
                code="not_eligible",
                details={"reasons": eligibility["reasons"]},
            )

        now = utcnow()
        doc = {
            "driveId": drive_id,
            "driveRole": drive.get("role"),
            "companyName": drive.get("companyName"),
            "studentId": student["id"],
            "studentName": student.get("name"),
            "studentEmail": student.get("email"),
            "collegeId": student.get("collegeId"),
            "batchId": student.get("batchId"),
            "batchName": student.get("batchName"),
            "status": ApplicationStatus.APPLIED.value,
            "currentRound": None,
            "roundResults": [],
            "offer": None,
            "coverNote": cover_note,
            "eligibilitySnapshot": eligibility,
            "appliedAt": now,
            "updatedAt": now,
        }
        application = self.repos.applications.create(doc, doc_id=f"{drive_id}_{student['id']}")

        admins = self.repos.users.by_role("admin", student.get("collegeId"))
        self.notifications.notify(
            [student.get("uid"), *[admin["id"] for admin in admins]],
            notification_type=NotificationType.APPLICATION,
            title=f"Application submitted — {drive.get('companyName')}",
            body=f"{student.get('name')} applied for {drive.get('role')}.",
            link=f"/applications/{application['id']}",
        )
        self.audit.record(
            actor, "application.apply", "application", application["id"], after={"driveId": drive_id}
        )
        return application

    # -- reads --------------------------------------------------------------
    def list(
        self,
        actor: Principal,
        *,
        drive_id: str | None = None,
        student_id: str | None = None,
        status: str | None = None,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> Page:
        if actor.role == Role.STUDENT:
            student = self.repos.students.by_uid(actor.uid)
            if not student:
                return Page(items=[], next_cursor=None)
            docs = self.repos.applications.for_student(student["id"], limit=500)
            if drive_id:
                docs = [d for d in docs if d.get("driveId") == drive_id]
            if status:
                docs = [d for d in docs if d.get("status") == status]
            return self._paginate(docs, limit, cursor)

        if actor.role == Role.TRAINER:
            batches = self.repos.batches.for_trainer(actor.uid, actor.college_ids)
            batch_ids = {b["id"] for b in batches}
            docs = [
                d
                for d in self.repos.applications.all(cap=20000)
                if d.get("batchId") in batch_ids
            ]
        else:
            filters: list[tuple[str, str, Any]] = []
            if drive_id:
                filters.append(("driveId", "==", drive_id))
            if status:
                filters.append(("status", "==", status))
            if student_id:
                filters.append(("studentId", "==", student_id))
            allowed = scoped_college_ids(actor)
            if allowed is not None:
                if not allowed:
                    return Page(items=[], next_cursor=None)
                filters.append(("collegeId", "in", allowed))
            docs = self.repos.applications.all(filters, cap=20000)

        if drive_id:
            docs = [d for d in docs if d.get("driveId") == drive_id]
        if student_id:
            docs = [d for d in docs if d.get("studentId") == student_id]
        if status:
            docs = [d for d in docs if d.get("status") == status]
        if actor.role == Role.TRAINER:
            for doc in docs:
                self._require_batch(actor, doc)

        return self._paginate(docs, limit, cursor)

    def get(self, actor: Principal, application_id: str) -> dict[str, Any]:
        application = self._application(application_id)
        self._ensure_read(actor, application)
        return self._with_letter_url(application)

    # -- round results ------------------------------------------------------
    def update_round(self, actor: Principal, application_id: str, payload: RoundUpdate) -> dict[str, Any]:
        if not actor.is_admin:
            raise Forbidden("Only admins can record round results", code="role_forbidden")
        application = self._application(application_id)
        drive = self._drive(application["driveId"])
        ensure_college(actor, application.get("collegeId"))

        try:
            status = RoundResultStatus(payload.status)
        except ValueError as exc:
            raise BadRequest(
                f"Round status must be one of: {', '.join(s.value for s in RoundResultStatus)}"
            ) from exc

        round_names = [r.get("name") for r in drive.get("rounds") or []]
        if round_names and payload.round_name not in round_names:
            raise BadRequest(
                f"Unknown round '{payload.round_name}'. Expected one of: {', '.join(round_names)}",
                code="unknown_round",
            )

        result = {
            "roundName": payload.round_name,
            "status": status.value,
            "score": payload.score,
            "remarks": payload.remarks,
            "recordedBy": actor.uid,
            "recordedByName": actor.name,
            "recordedAt": utcnow().isoformat(),
        }
        results = [r for r in (application.get("roundResults") or []) if r.get("roundName") != payload.round_name]
        results.append(result)

        if status in {RoundResultStatus.REJECTED, RoundResultStatus.ABSENT}:
            new_status = ApplicationStatus.REJECTED
        elif status == RoundResultStatus.CLEARED:
            new_status = ApplicationStatus.IN_PROCESS
        else:
            new_status = ApplicationStatus.SHORTLISTED

        updated = self.repos.applications.update(
            application_id,
            {
                "roundResults": results,
                "currentRound": payload.round_name,
                "status": new_status.value,
                "updatedAt": utcnow(),
            },
        )

        self.notifications.notify(
            [application.get("studentId")],
            notification_type=NotificationType.APPLICATION,
            title=f"{payload.round_name} result — {application.get('companyName')}",
            body=f"Your application moved to {new_status.value.replace('_', ' ')}.",
            link=f"/applications/{application_id}",
        )
        self.audit.record(
            actor,
            "application.round",
            "application",
            application_id,
            before={"status": application.get("status")},
            after={"round": payload.round_name, "roundStatus": status.value, "status": new_status.value},
        )
        return self._with_letter_url(updated)

    # -- outcomes -----------------------------------------------------------
    def update_outcome(self, actor: Principal, application_id: str, payload: OutcomeUpdate) -> dict[str, Any]:
        application = self._application(application_id)
        drive = self._drive(application["driveId"])

        if payload.outcome == "withdrawn":
            if actor.role == Role.STUDENT and application.get("studentId") != self._student_id(actor):
                raise Forbidden("You can only withdraw your own application", code="application_forbidden")
            if actor.role not in {Role.STUDENT, Role.ADMIN}:
                raise Forbidden("Only the student or an admin can withdraw", code="role_forbidden")
            if actor.role == Role.ADMIN:
                ensure_college(actor, application.get("collegeId"))
        else:
            if not actor.is_admin:
                raise Forbidden("Only admins can record outcomes", code="role_forbidden")
            ensure_college(actor, application.get("collegeId"))

        if application.get("status") in {
            ApplicationStatus.WITHDRAWN.value,
        }:
            raise Conflict("This application was withdrawn", code="application_withdrawn")

        student = self.repos.students.require(application.get("studentId"), "Student")
        before = {"status": application.get("status"), "offer": application.get("offer")}
        now = utcnow()

        if payload.outcome == "selected":
            if student.get("placementStatus") == PlacementStatus.PLACED.value and not payload.override_lock:
                raise Conflict(
                    "Student is already placed. Set overrideLock to allow a dream offer.",
                    code="placement_locked",
                )
            ctc = payload.ctc if payload.ctc is not None else float(drive.get("ctc") or 0)
            offer = {
                "ctc": ctc,
                "offerDate": payload.offer_date,
                "letterPath": (application.get("offer") or {}).get("letterPath"),
                "joined": None,
            }
            updated = self.repos.applications.update(
                application_id,
                {
                    "status": ApplicationStatus.SELECTED.value,
                    "offer": offer,
                    "outcomeNotes": payload.notes,
                    "updatedAt": now,
                },
            )
            self.metrics.mark_placed(
                student["id"],
                company=drive.get("companyName") or "",
                ctc=ctc,
                lock=not payload.override_lock,
            )
            self.notifications.notify(
                [student.get("uid")],
                notification_type=NotificationType.APPLICATION,
                title=f"Selected at {drive.get('companyName')} 🎉",
                body=f"Congratulations! Offer CTC: {ctc} LPA.",
                link=f"/applications/{application_id}",
                email=True,
            )
        elif payload.outcome == "rejected":
            updated = self.repos.applications.update(
                application_id,
                {
                    "status": ApplicationStatus.REJECTED.value,
                    "outcomeNotes": payload.notes,
                    "updatedAt": now,
                },
            )
            self._unplace_if_needed(student, drive)
            self.notifications.notify(
                [student.get("uid")],
                notification_type=NotificationType.APPLICATION,
                title=f"Application update — {drive.get('companyName')}",
                body="The company did not move forward with your application.",
                link=f"/applications/{application_id}",
            )
        else:  # withdrawn
            updated = self.repos.applications.update(
                application_id,
                {
                    "status": ApplicationStatus.WITHDRAWN.value,
                    "outcomeNotes": payload.notes,
                    "updatedAt": now,
                },
            )
            self._unplace_if_needed(student, drive)
            self.notifications.notify(
                [student.get("uid")],
                notification_type=NotificationType.APPLICATION,
                title=f"Application withdrawn — {drive.get('companyName')}",
                body="Your application was withdrawn.",
                link=f"/applications/{application_id}",
            )

        self.audit.record(
            actor,
            "application.outcome",
            "application",
            application_id,
            before=before,
            after={"status": payload.outcome, "ctc": payload.ctc, "overrideLock": payload.override_lock},
        )
        return self._with_letter_url(updated)

    # -- offer letters ------------------------------------------------------
    async def upload_offer_letter(self, actor: Principal, application_id: str, upload: Any) -> dict[str, Any]:
        if not actor.is_admin:
            raise Forbidden("Only admins can upload offer letters", code="role_forbidden")
        application = self._application(application_id)
        if application.get("status") != ApplicationStatus.SELECTED.value:
            raise BadRequest("Offer letters can only be uploaded for selected applications")
        ensure_college(actor, application.get("collegeId"))

        path = await self.files.upload_offer_letter(
            college_id=application.get("collegeId"),
            application_id=application_id,
            upload=upload,
        )
        offer = dict(application.get("offer") or {})
        offer["letterPath"] = path
        updated = self.repos.applications.update(
            application_id, {"offer": offer, "updatedAt": utcnow()}
        )
        self.notifications.notify(
            [application.get("studentId")],
            notification_type=NotificationType.APPLICATION,
            title="Offer letter available",
            body=f"Your offer letter from {application.get('companyName')} is ready to download.",
            link=f"/applications/{application_id}",
        )
        self.audit.record(actor, "application.offer_letter", "application", application_id)
        return {
            "offerLetterPath": path,
            "offerLetterUrl": self.files.signed_url(path),
        }

    def offer_letter_url(self, actor: Principal, application_id: str) -> dict[str, Any]:
        application = self._application(application_id)
        self._ensure_read(actor, application)
        path = (application.get("offer") or {}).get("letterPath")
        if not path:
            raise NotFound("No offer letter on file", code="offer_letter_not_found")
        return {"offerLetterPath": path, "offerLetterUrl": self.files.signed_url(path)}

    # -- helpers ------------------------------------------------------------
    def _application(self, application_id: str) -> dict[str, Any]:
        application = self.repos.applications.get(application_id)
        if application is None:
            raise NotFound(f"Application {application_id} not found", code="application_not_found")
        return application

    def _drive(self, drive_id: str) -> dict[str, Any]:
        drive = self.repos.drives.get(drive_id)
        if drive is None:
            raise NotFound(f"Drive {drive_id} not found", code="drive_not_found")
        return drive

    def _student_id(self, actor: Principal) -> str | None:
        student = self.repos.students.by_uid(actor.uid)
        return student["id"] if student else None

    def _require_batch(self, actor: Principal, application: dict[str, Any]) -> None:
        batch = self.repos.batches.get(application.get("batchId") or "")
        if batch is None or actor.uid not in (batch.get("trainerIds") or []):
            raise Forbidden("You are not assigned to this student's batch", code="batch_forbidden")

    def _ensure_read(self, actor: Principal, application: dict[str, Any]) -> None:
        if actor.role == Role.STUDENT:
            if application.get("studentId") != self._student_id(actor):
                raise Forbidden("You can only view your own applications", code="application_forbidden")
            return
        if actor.role == Role.ADMIN:
            ensure_college(actor, application.get("collegeId"))
            return
        self._require_batch(actor, application)

    def _unplace_if_needed(self, student: dict[str, Any], drive: dict[str, Any]) -> None:
        if (
            student.get("placementStatus") == PlacementStatus.PLACED.value
            and student.get("placedCompany") == drive.get("companyName")
        ):
            self.repos.students.update(
                student["id"],
                {
                    "placementStatus": PlacementStatus.UNPLACED.value,
                    "placedCompany": None,
                    "placedCtc": None,
                    "placementLocked": False,
                    "updatedAt": utcnow(),
                },
            )

    def _with_letter_url(self, application: dict[str, Any]) -> dict[str, Any]:
        doc = dict(application)
        offer = doc.get("offer")
        if offer and offer.get("letterPath"):
            offer = dict(offer)
            offer["letterUrl"] = self.files.signed_url(offer["letterPath"])
            doc["offer"] = offer
        return doc

    def _paginate(
        self, docs: list[dict[str, Any]], limit: int | None, cursor: str | None
    ) -> Page:
        docs.sort(key=lambda d: (d.get("appliedAt") is not None, d.get("appliedAt"), d["id"]), reverse=True)
        page = paginate_items(docs, order_by="appliedAt", limit=limit, cursor=cursor)
        page.items = [self._with_letter_url(d) for d in page.items]
        return page
