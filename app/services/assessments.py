"""Assessments, score entry and student score views (FR-19 to FR-21)."""

from __future__ import annotations

from typing import Any

from app.core.errors import BadRequest, Forbidden, NotFound
from app.core.pagination import Page
from app.core.scoping import ensure_batch_access, ensure_college, ensure_student_access, scoped_college_ids
from app.core.security import Principal
from app.models.assessment import AssessmentCreate, AssessmentUpdate, ScoreBulkRequest
from app.models.enums import Role
from app.repositories import Repos
from app.services.audit import AuditService
from app.services.csv_utils import parse_csv
from app.services.metrics import MetricsService, assessment_average, ratio, utcnow


class AssessmentsService:
    def __init__(
        self, repos: Repos, *, audit: AuditService | None = None, metrics: MetricsService | None = None
    ) -> None:
        self.repos = repos
        self.audit = audit or AuditService(repos)
        self.metrics = metrics or MetricsService(repos)

    # -- assessments --------------------------------------------------------
    def list(
        self,
        actor: Principal,
        *,
        batch_id: str | None = None,
        college_id: str | None = None,
        assessment_type: str | None = None,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> Page:
        filters: list[tuple[str, str, Any]] = []
        if actor.role == Role.STUDENT:
            student = self.repos.students.by_uid(actor.uid)
            if not student or not student.get("batchId"):
                return Page(items=[], next_cursor=None)
            filters.append(("batchId", "==", student["batchId"]))
        elif actor.role == Role.TRAINER:
            batches = self.repos.batches.for_trainer(actor.uid, actor.college_ids)
            ids = [b["id"] for b in batches]
            if batch_id:
                if batch_id not in ids:
                    raise Forbidden("You are not assigned to this batch", code="batch_forbidden")
                ids = [batch_id]
            if not ids:
                return Page(items=[], next_cursor=None)
            filters.append(("batchId", "in", ids))
        elif batch_id:
            filters.append(("batchId", "==", batch_id))

        if college_id:
            if actor.role != Role.STUDENT:
                ensure_college(actor, college_id)
            filters.append(("collegeId", "==", college_id))
        elif actor.role == Role.ADMIN:
            allowed = scoped_college_ids(actor)
            if allowed is not None:
                if not allowed:
                    return Page(items=[], next_cursor=None)
                filters.append(("collegeId", "in", allowed))
        if assessment_type:
            filters.append(("type", "==", assessment_type))

        return self.repos.assessments.list(
            filters, order_by="date", descending=True, limit=limit, cursor=cursor
        )

    def get(self, actor: Principal, assessment_id: str) -> dict[str, Any]:
        assessment, batch = self._context(assessment_id)
        self._ensure_read(actor, assessment, batch)
        assessment = dict(assessment)
        assessment["scoredCount"] = len(self.repos.scores.for_assessment(assessment_id))
        return assessment

    def create(self, actor: Principal, payload: AssessmentCreate) -> dict[str, Any]:
        batch = self.repos.batches.get(payload.batch_id)
        if batch is None:
            raise NotFound(f"Batch {payload.batch_id} not found", code="batch_not_found")
        ensure_batch_access(actor, batch, write=True)

        now = utcnow()
        doc = {
            **payload.model_dump(by_alias=True),
            "batchName": batch.get("name"),
            "collegeId": batch["collegeId"],
            "createdBy": actor.uid,
            "createdAt": now,
            "updatedAt": now,
        }
        assessment = self.repos.assessments.create(doc)
        self.audit.record(
            actor, "assessment.create", "assessment", assessment["id"], after={"title": payload.title}
        )
        return assessment

    def update(self, actor: Principal, assessment_id: str, payload: AssessmentUpdate) -> dict[str, Any]:
        assessment, batch = self._context(assessment_id)
        ensure_batch_access(actor, batch, write=True)

        patch = payload.model_dump(exclude_unset=True, by_alias=True)
        if not patch:
            return assessment
        if "maxMarks" in patch:
            over = [
                score
                for score in self.repos.scores.for_assessment(assessment_id)
                if float(score.get("marks") or 0) > float(patch["maxMarks"])
            ]
            if over:
                raise BadRequest(
                    f"{len(over)} existing score(s) exceed the new maximum marks",
                    code="scores_exceed_max",
                )

        patch["updatedAt"] = utcnow()
        updated = self.repos.assessments.update(assessment_id, patch)
        if "maxMarks" in patch or "weightage" in patch:
            self._refresh_batch(assessment["batchId"])

        self.audit.record(actor, "assessment.update", "assessment", assessment_id, after=patch)
        return updated

    # -- scores -------------------------------------------------------------
    def save_scores(
        self, actor: Principal, assessment_id: str, payload: ScoreBulkRequest
    ) -> dict[str, Any]:
        assessment, batch = self._context(assessment_id)
        ensure_batch_access(actor, batch, write=True)
        return self._upsert_scores(actor, assessment, batch, [r.model_dump() for r in payload.records])

    def import_scores_csv(self, actor: Principal, assessment_id: str, data: bytes) -> dict[str, Any]:
        assessment, batch = self._context(assessment_id)
        ensure_batch_access(actor, batch, write=True)

        rows = parse_csv(data, required={"marks"}, max_rows=500)
        students = self.repos.students.for_batch(batch["id"], limit=5000)
        by_roll = {s.get("rollNo"): s for s in students if s.get("rollNo")}
        by_id = {s["id"]: s for s in students}
        by_email = {s.get("email"): s for s in students if s.get("email")}

        records: list[dict[str, Any]] = []
        errors: list[dict[str, Any]] = []
        for index, row in enumerate(rows, start=2):
            student = (
                by_id.get(row.get("studentid") or "")
                or by_roll.get(row.get("rollno") or "")
                or by_email.get(row.get("email") or "")
            )
            if student is None:
                errors.append({"row": index, "message": "Student not found in batch"})
                continue
            try:
                marks = float(row.get("marks") or "")
            except ValueError:
                errors.append({"row": index, "message": "marks must be a number"})
                continue
            records.append(
                {"student_id": student["id"], "marks": marks, "remarks": row.get("remarks") or None}
            )

        result = self._upsert_scores(actor, assessment, batch, records, allow_partial=True)
        return {**result, "errors": errors + result.get("errors", [])}

    def list_scores(self, actor: Principal, assessment_id: str) -> list[dict[str, Any]]:
        assessment, batch = self._context(assessment_id)
        ensure_batch_access(actor, batch, write=False)
        scores = self.repos.scores.for_assessment(assessment_id)
        scores.sort(key=lambda s: (s.get("studentName") or ""))
        return scores

    def student_scores(self, actor: Principal, student_id: str) -> dict[str, Any]:
        student = self.repos.students.require(student_id, "Student")
        batch = self.repos.batches.get(student["batchId"]) if student.get("batchId") else None
        ensure_student_access(actor, student, batch=batch)

        scores = self.repos.scores.for_student(student_id)
        items = []
        for score in scores:
            assessment = self.repos.assessments.get(score["assessmentId"])
            if assessment is None:
                continue
            class_scores = self.repos.scores.for_assessment(assessment["id"])
            percentages = [
                float(s.get("marks") or 0) / float(s.get("maxMarks") or assessment["maxMarks"]) * 100
                for s in class_scores
                if float(s.get("maxMarks") or assessment.get("maxMarks") or 0) > 0
            ]
            my_pct = float(score.get("marks") or 0) / float(assessment["maxMarks"]) * 100
            rank_band = _rank_band(my_pct, percentages)
            items.append(
                {
                    "assessmentId": assessment["id"],
                    "title": assessment["title"],
                    "type": assessment["type"],
                    "date": assessment["date"],
                    "marks": score.get("marks"),
                    "maxMarks": assessment["maxMarks"],
                    "percentage": round(my_pct, 1),
                    "classAverage": round(sum(percentages) / len(percentages), 1) if percentages else 0.0,
                    "rankBand": rank_band,
                    "remarks": score.get("remarks"),
                }
            )
        items.sort(key=lambda i: i["date"], reverse=True)
        return {
            "studentId": student_id,
            "overallAverage": assessment_average(scores),
            "items": items,
        }

    def analytics(self, actor: Principal, assessment_id: str) -> dict[str, Any]:
        assessment, batch = self._context(assessment_id)
        ensure_batch_access(actor, batch)

        scores = self.repos.scores.for_assessment(assessment_id)
        percentages = [
            float(s.get("marks") or 0) / float(assessment["maxMarks"]) * 100 for s in scores
        ]
        buckets = [
            {"label": "0-20", "count": 0},
            {"label": "20-40", "count": 0},
            {"label": "40-60", "count": 0},
            {"label": "60-80", "count": 0},
            {"label": "80-100", "count": 0},
        ]
        for pct in percentages:
            index = min(int(pct // 20), 4)
            buckets[index]["count"] += 1

        return {
            "assessmentId": assessment_id,
            "title": assessment["title"],
            "batchId": assessment["batchId"],
            "maxMarks": assessment["maxMarks"],
            "scored": len(scores),
            "average": round(sum(percentages) / len(percentages), 1) if percentages else 0.0,
            "highest": round(max(percentages), 1) if percentages else 0.0,
            "lowest": round(min(percentages), 1) if percentages else 0.0,
            "passRate": ratio(sum(1 for p in percentages if p >= 40), len(percentages)),
            "distribution": buckets,
        }

    # -- helpers ------------------------------------------------------------
    def _context(self, assessment_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
        assessment = self.repos.assessments.get(assessment_id)
        if assessment is None:
            raise NotFound(f"Assessment {assessment_id} not found", code="assessment_not_found")
        batch = self.repos.batches.get(assessment["batchId"])
        if batch is None:
            raise NotFound(f"Batch {assessment['batchId']} not found", code="batch_not_found")
        return assessment, batch

    def _ensure_read(
        self, actor: Principal, assessment: dict[str, Any], batch: dict[str, Any]
    ) -> None:
        if actor.role == Role.STUDENT:
            student = self.repos.students.by_uid(actor.uid)
            if not student or student.get("batchId") != assessment["batchId"]:
                raise Forbidden("You can only view assessments for your batch", code="batch_forbidden")
            return
        ensure_batch_access(actor, batch)

    def _upsert_scores(
        self,
        actor: Principal,
        assessment: dict[str, Any],
        batch: dict[str, Any],
        records: list[dict[str, Any]],
        *,
        allow_partial: bool = False,
    ) -> dict[str, Any]:
        students = {s["id"]: s for s in self.repos.students.for_batch(batch["id"], limit=5000)}
        max_marks = float(assessment["maxMarks"])
        now = utcnow()
        saved = 0
        errors: list[dict[str, Any]] = []
        touched: list[str] = []

        for record in records:
            student_id = record.get("student_id") or record.get("studentId")
            marks = record.get("marks")
            try:
                if student_id not in students:
                    raise BadRequest(f"Student {student_id} is not in this batch", code="student_batch_mismatch")
                if marks is None or float(marks) < 0 or float(marks) > max_marks:
                    raise BadRequest(f"Marks must be between 0 and {max_marks}", code="invalid_marks")
            except BadRequest as exc:
                if allow_partial:
                    errors.append({"row": None, "message": exc.message, "studentId": student_id})
                    continue
                raise

            student = students[student_id]
            doc_id = f"{assessment['id']}_{student_id}"
            existing = self.repos.scores.get(doc_id)
            self.repos.scores.set(
                {
                    "assessmentId": assessment["id"],
                    "assessmentTitle": assessment.get("title"),
                    "assessmentType": assessment.get("type"),
                    "assessmentDate": assessment.get("date"),
                    "batchId": batch["id"],
                    "studentId": student_id,
                    "studentName": student.get("name"),
                    "marks": float(marks),
                    "maxMarks": max_marks,
                    "weightage": float(assessment.get("weightage") or 1.0),
                    "remarks": record.get("remarks"),
                    "updatedBy": actor.uid,
                    "createdAt": (existing or {}).get("createdAt", now),
                    "updatedAt": now,
                },
                doc_id=doc_id,
            )
            saved += 1
            touched.append(student_id)

        for student_id in dict.fromkeys(touched):
            self.metrics.refresh_student(student_id)

        self.audit.record(
            actor,
            "assessment.scores",
            "assessment",
            assessment["id"],
            after={"saved": saved, "studentIds": list(dict.fromkeys(touched))},
        )
        return {"assessmentId": assessment["id"], "saved": saved, "errors": errors}

    def _refresh_batch(self, batch_id: str) -> None:
        for student in self.repos.students.for_batch(batch_id, limit=5000):
            self.metrics.refresh_student(student["id"])


def _rank_band(my_percentage: float, all_percentages: list[float]) -> str:
    if not all_percentages:
        return "unranked"
    higher = sum(1 for pct in all_percentages if pct > my_percentage)
    denominator = max(len(all_percentages) - 1, 1)
    percentile = higher / denominator
    if percentile <= 0.10:
        return "top_10_percent"
    if percentile <= 0.25:
        return "top_25_percent"
    if percentile <= 0.50:
        return "top_50_percent"
    return "bottom_50_percent"
