"""Service dependency wiring for routers."""

from __future__ import annotations

from typing import Any

from fastapi import Depends

from app.core.pagination import Page
from app.repositories import Repos, get_repos
from app.services.analytics import AnalyticsService
from app.services.applications import ApplicationsService
from app.services.assessments import AssessmentsService
from app.services.attendance import AttendanceService
from app.services.audit import AuditService
from app.services.auth import AuthService
from app.services.batches import BatchesService
from app.services.colleges import CollegesService
from app.services.companies import CompaniesService
from app.services.drives import DrivesService
from app.services.feedback import FeedbackService
from app.services.notify import NotificationService
from app.services.reports import ReportsService
from app.services.students import StudentsService
from app.services.users import UsersService


def get_auth_service(repos: Repos = Depends(get_repos)) -> AuthService:
    return AuthService(repos)


def get_users_service(repos: Repos = Depends(get_repos)) -> UsersService:
    return UsersService(repos)


def get_colleges_service(repos: Repos = Depends(get_repos)) -> CollegesService:
    return CollegesService(repos)


def get_batches_service(repos: Repos = Depends(get_repos)) -> BatchesService:
    return BatchesService(repos)


def get_students_service(repos: Repos = Depends(get_repos)) -> StudentsService:
    return StudentsService(repos)


def get_attendance_service(repos: Repos = Depends(get_repos)) -> AttendanceService:
    return AttendanceService(repos)


def get_assessments_service(repos: Repos = Depends(get_repos)) -> AssessmentsService:
    return AssessmentsService(repos)


def get_companies_service(repos: Repos = Depends(get_repos)) -> CompaniesService:
    return CompaniesService(repos)


def get_drives_service(repos: Repos = Depends(get_repos)) -> DrivesService:
    return DrivesService(repos)


def get_applications_service(repos: Repos = Depends(get_repos)) -> ApplicationsService:
    return ApplicationsService(repos)


def get_feedback_service(repos: Repos = Depends(get_repos)) -> FeedbackService:
    return FeedbackService(repos)


def get_analytics_service(repos: Repos = Depends(get_repos)) -> AnalyticsService:
    return AnalyticsService(repos)


def get_reports_service(repos: Repos = Depends(get_repos)) -> ReportsService:
    return ReportsService(repos)


def get_notifications_service(repos: Repos = Depends(get_repos)) -> NotificationService:
    return NotificationService(repos)


def get_audit_service(repos: Repos = Depends(get_repos)) -> AuditService:
    return AuditService(repos)


def as_page(page: Page) -> dict[str, Any]:
    return {"items": page.items, "nextCursor": page.next_cursor}
