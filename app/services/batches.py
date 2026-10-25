"""Batches: CRUD, trainer assignment, student movement with history (FR-8, FR-9)."""

from __future__ import annotations

from datetime import date
from typing import Any

from app.core.config import settings
from app.core.errors import BadRequest, Forbidden, NotFound
from app.core.pagination import Page, paginate_items
from app.core.scoping import ensure_batch_access, ensure_college, scoped_college_ids
from app.core.security import Principal
from app.models.enums import Role
from app.models.student import AssignStudentsRequest, BatchCreate, BatchUpdate
from app.repositories import Repos
from app.services.audit import AuditService
from app.services.metrics import utcnow


class BatchesService:
    def __init__(self, repos: Repos, audit: AuditService | None = None) -> None:
        self.repos = repos
        self.audit = audit or AuditService(repos)

    # -- reads --------------------------------------------------------------
    def list(
        self,
        actor: Principal,
        *,
        college_id: str | None = None,
        trainer_id: str | None = None,
        status: str | None = None,
        q: str | None = None,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> Page:
        if actor.role == Role.STUDENT:
            student = self.repos.students.by_uid(actor.uid)
            docs = []
            if student and student.get("batchId"):
                batch = self.repos.batches.get(student["batchId"])
                docs = [batch] if batch else []
            return paginate_items([self._decorate(d) for d in docs], order_by="startDate", limit=limit, cursor=cursor)

        docs: list[dict[str, Any]]
        if actor.role == Role.TRAINER:
            docs = self.repos.batches.for_trainer(actor.uid, actor.college_ids)
        else:
            if college_id:
                ensure_college(actor, college_id)
                docs = self.repos.batches.for_college(college_id, limit=5000)
            else:
                allowed = scoped_college_ids(actor)
                if allowed is None:
                    docs = self.repos.batches.all(cap=5000)
                elif not allowed:
                    return Page(items=[], next_cursor=None)
                else:
                    docs = self.repos.batches.all([("collegeId", "in", allowed)], cap=5000)

        if college_id:
            ensure_college(actor, college_id)
            docs = [d for d in docs if d.get("collegeId") == college_id]
        if trainer_id:
            docs = [d for d in docs if trainer_id in (d.get("trainerIds") or [])]
        if status:
            docs = [d for d in docs if d.get("status") == status]
        if q:
            needle = q.lower()
            docs = [d for d in docs if needle in (d.get("name") or "").lower()]

        docs.sort(key=lambda d: (d.get("startDate") or "", d["id"]), reverse=True)
        return paginate_items(
            [self._decorate(d) for d in docs],
            order_by="startDate",
            limit=limit,
            cursor=cursor,
        )

    def get(self, actor: Principal, batch_id: str) -> dict[str, Any]:
        batch = self._require_batch(batch_id)
        if actor.role == Role.STUDENT:
            student = self.repos.students.by_uid(actor.uid)
            if not student or student.get("batchId") != batch_id:
                raise Forbidden("You can only view your own batch", code="batch_forbidden")
        else:
            ensure_batch_access(actor, batch)
        decorated = self._decorate(batch)
        decorated["studentCount"] = self.repos.students.count([("batchId", "==", batch_id)])
        return decorated

    # -- writes -------------------------------------------------------------
    def create(self, actor: Principal, payload: BatchCreate) -> dict[str, Any]:
        if not actor.is_admin:
            raise Forbidden("Only admins can create batches", code="role_forbidden")
        ensure_college(actor, payload.college_id)
        if self.repos.colleges.get(payload.college_id) is None:
            raise BadRequest(f"College {payload.college_id} not found", code="college_not_found")
        self._validate_dates(payload.start_date, payload.end_date)
        trainer_names = self._validate_trainers(payload.college_id, payload.trainer_ids)

        now = utcnow()
        doc = {
            **payload.model_dump(by_alias=True),
            "collegeName": self.repos.colleges.require(payload.college_id, "College").get("name"),
            "trainerNames": trainer_names,
            "studentCount": 0,
            "createdAt": now,
            "updatedAt": now,
            "createdBy": actor.uid,
        }
        batch = self.repos.batches.create(doc)
        self.audit.record(actor, "batch.create", "batch", batch["id"], after={"name": batch["name"]})
        return self._decorate(batch)

    def update(self, actor: Principal, batch_id: str, payload: BatchUpdate) -> dict[str, Any]:
        if not actor.is_admin:
            raise Forbidden("Only admins can update batches", code="role_forbidden")
        batch = self._require_batch(batch_id)
        ensure_college(actor, batch.get("collegeId"))

        patch = payload.model_dump(exclude_unset=True, by_alias=True)
        if not patch:
            return self._decorate(batch)

        start = patch.get("startDate", batch.get("startDate"))
        end = patch.get("endDate", batch.get("endDate"))
        self._validate_dates(start, end)

        if "trainerIds" in patch:
            patch["trainerNames"] = self._validate_trainers(batch["collegeId"], patch["trainerIds"])

        patch["updatedAt"] = utcnow()
        updated = self.repos.batches.update(batch_id, patch)

        if "name" in patch and patch["name"] != batch.get("name"):
            self._propagate_name(batch_id, patch["name"])
        if "minAttendancePct" in patch:
            self._recompute_at_risk(batch_id, float(patch["minAttendancePct"]))

        self.audit.record(
            actor,
            "batch.update",
            "batch",
            batch_id,
            before={key: batch.get(key) for key in patch if key != "updatedAt"},
            after=patch,
        )
        return self._decorate(updated)

    def archive(self, actor: Principal, batch_id: str) -> dict[str, Any]:
        if not actor.is_admin:
            raise Forbidden("Only admins can archive batches", code="role_forbidden")
        batch = self._require_batch(batch_id)
        ensure_college(actor, batch.get("collegeId"))
        updated = self.repos.batches.update(
            batch_id, {"status": "archived", "updatedAt": utcnow()}
        )
        self.audit.record(actor, "batch.archive", "batch", batch_id, after={"status": "archived"})
        return self._decorate(updated)

    def assign_students(
        self, actor: Principal, batch_id: str, payload: AssignStudentsRequest
    ) -> dict[str, Any]:
        batch = self._require_batch(batch_id)
        if actor.role == Role.ADMIN:
            ensure_college(actor, batch.get("collegeId"))
        elif actor.role == Role.TRAINER:
            ensure_batch_access(actor, batch)
        else:
            raise Forbidden("Students cannot be reassigned by students", code="role_forbidden")

        if len(payload.student_ids) > 500:
            raise BadRequest("At most 500 students can be assigned per request")

        now = utcnow()
        history_ids: list[str] = []
        affected_batches: set[str] = set()
        assigned = 0

        for student_id in dict.fromkeys(payload.student_ids):
            student = self.repos.students.require(student_id, "Student")
            if student.get("collegeId") != batch.get("collegeId"):
                raise BadRequest(
                    f"Student {student_id} belongs to a different college",
                    code="college_mismatch",
                )
            previous_batch_id = student.get("batchId")
            if previous_batch_id == batch_id:
                continue
            if previous_batch_id and not payload.move:
                continue

            self.repos.students.update(
                student_id,
                {"batchId": batch_id, "batchName": batch.get("name"), "updatedAt": now},
            )
            history = self.repos.batch_history.create(
                {
                    "studentId": student_id,
                    "fromBatchId": previous_batch_id,
                    "toBatchId": batch_id,
                    "movedBy": actor.uid,
                    "movedAt": now,
                }
            )
            history_ids.append(history["id"])
            assigned += 1
            affected_batches.add(batch_id)
            if previous_batch_id:
                affected_batches.add(previous_batch_id)
            self._apply_at_risk(student_id, batch)

        for affected in affected_batches:
            self._recount(affected)

        self.audit.record(
            actor,
            "batch.assign_students",
            "batch",
            batch_id,
            after={"studentIds": list(dict.fromkeys(payload.student_ids)), "assigned": assigned},
        )
        return {"assigned": assigned, "historyIds": history_ids}

    # -- helpers ------------------------------------------------------------
    def _require_batch(self, batch_id: str) -> dict[str, Any]:
        batch = self.repos.batches.get(batch_id)
        if batch is None:
            raise NotFound(f"Batch {batch_id} not found", code="batch_not_found")
        return batch

    def _decorate(self, batch: dict[str, Any]) -> dict[str, Any]:
        doc = dict(batch)
        trainer_ids = doc.get("trainerIds") or []
        if not doc.get("trainerNames") and trainer_ids:
            doc["trainerNames"] = [
                (self.repos.users.get(tid) or {}).get("name", tid) for tid in trainer_ids
            ]
        doc.setdefault("studentCount", 0)
        return doc

    def _validate_dates(self, start: str | None, end: str | None) -> None:
        try:
            start_date = date.fromisoformat(start) if start else None
            end_date = date.fromisoformat(end) if end else None
        except ValueError as exc:
            raise BadRequest("Dates must be ISO formatted (YYYY-MM-DD)") from exc
        if start_date and end_date and end_date < start_date:
            raise BadRequest("Batch end date cannot be before the start date", code="invalid_date_range")

    def _validate_trainers(self, college_id: str, trainer_ids: list[str]) -> list[str]:
        names: list[str] = []
        for trainer_id in dict.fromkeys(trainer_ids or []):
            trainer = self.repos.users.get(trainer_id)
            if trainer is None:
                raise BadRequest(f"Trainer {trainer_id} not found", code="trainer_not_found")
            if trainer.get("role") != Role.TRAINER.value:
                raise BadRequest(f"User {trainer_id} is not a trainer", code="invalid_trainer")
            if college_id not in (trainer.get("collegeIds") or []):
                raise BadRequest(
                    f"Trainer {trainer_id} is not assigned to this college",
                    code="trainer_college_mismatch",
                )
            names.append(trainer.get("name") or trainer_id)
        return names

    def _propagate_name(self, batch_id: str, name: str) -> None:
        students = self.repos.students.for_batch(batch_id, limit=5000)
        now = utcnow()
        for start in range(0, len(students), 500):
            self.repos.students.write_batch(
                [
                    ("update", student["id"], {"batchName": name, "updatedAt": now})
                    for student in students[start : start + 500]
                ]
            )

    def _recount(self, batch_id: str) -> None:
        if self.repos.batches.get(batch_id) is None:
            return
        total = self.repos.students.count([("batchId", "==", batch_id)])
        self.repos.batches.update(batch_id, {"studentCount": total, "updatedAt": utcnow()})

    def _apply_at_risk(self, student_id: str, batch: dict[str, Any]) -> None:
        student = self.repos.students.get(student_id)
        if not student:
            return
        threshold = float(batch.get("minAttendancePct") or settings.default_min_attendance_pct)
        has_attendance = self.repos.attendance.count([("studentId", "==", student_id)]) > 0
        at_risk = has_attendance and float(student.get("attendancePct") or 0) < threshold
        if bool(student.get("atRisk")) != at_risk:
            self.repos.students.update(student_id, {"atRisk": at_risk, "updatedAt": utcnow()})

    def _recompute_at_risk(self, batch_id: str, threshold: float) -> None:
        for student in self.repos.students.for_batch(batch_id, limit=5000):
            has_attendance = self.repos.attendance.count([("studentId", "==", student["id"])]) > 0
            at_risk = has_attendance and float(student.get("attendancePct") or 0) < threshold
            if bool(student.get("atRisk")) != at_risk:
                self.repos.students.update(student["id"], {"atRisk": at_risk, "updatedAt": utcnow()})
