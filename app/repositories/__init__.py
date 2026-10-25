"""Repository bundle injected into services."""

from __future__ import annotations

from fastapi import Depends

from app.repositories.repositories import (
    ApplicationsRepo,
    AssessmentsRepo,
    AttendanceRepo,
    AuditRepo,
    BatchHistoryRepo,
    BatchesRepo,
    CollegesRepo,
    CompaniesRepo,
    DrivesRepo,
    FeedbackRepo,
    NotificationsRepo,
    ScoresRepo,
    SessionsRepo,
    SnapshotsRepo,
    StudentsRepo,
    UsersRepo,
)
from app.repositories.store import DocumentStore, get_store


class Repos:
    def __init__(self, store: DocumentStore) -> None:
        self.store = store
        self.users = UsersRepo(store)
        self.colleges = CollegesRepo(store)
        self.batches = BatchesRepo(store)
        self.students = StudentsRepo(store)
        self.sessions = SessionsRepo(store)
        self.attendance = AttendanceRepo(store)
        self.assessments = AssessmentsRepo(store)
        self.scores = ScoresRepo(store)
        self.companies = CompaniesRepo(store)
        self.drives = DrivesRepo(store)
        self.applications = ApplicationsRepo(store)
        self.feedback = FeedbackRepo(store)
        self.notifications = NotificationsRepo(store)
        self.audit = AuditRepo(store)
        self.snapshots = SnapshotsRepo(store)
        self.batch_history = BatchHistoryRepo(store)


def get_repos(store: DocumentStore = Depends(get_store)) -> Repos:
    return Repos(store)
