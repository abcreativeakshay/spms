"""Startup cache warm-up.

The read cache only helps if its keys match the queries screens actually make,
and the cache key includes filters, ordering and page size. Instead of copying
every query here (and letting it drift from the services), this calls the same
service ``list`` methods with a synthetic super-admin principal and the page
sizes the web client uses.

Warming runs on a background thread: the API accepts requests immediately and
any failure is only logged. Entries are served fresh for the cache TTL and are
then refreshed in the background (stale-while-revalidate).
"""

from __future__ import annotations

import logging
from typing import Callable

from app.core.config import settings
from app.core.security import Principal
from app.models.enums import Role
from app.repositories import Repos
from app.repositories.store import DocumentStore, FirestoreStore
from app.services.analytics import AnalyticsService
from app.services.applications import ApplicationsService
from app.services.batches import BatchesService
from app.services.colleges import CollegesService
from app.services.companies import CompaniesService
from app.services.drives import DrivesService
from app.services.students import StudentsService
from app.services.users import UsersService

logger = logging.getLogger("spms")

# Only used for read-only list calls; never persisted or authenticated.
WARM_ACTOR = Principal(uid="cache-warmup", role=Role.ADMIN, college_ids=["*"], super_admin=True)


def _steps(repos: Repos) -> list[tuple[str, Callable[[], object]]]:
    colleges = CollegesService(repos)
    companies = CompaniesService(repos)
    batches = BatchesService(repos)
    students = StudentsService(repos)
    users = UsersService(repos)
    drives = DrivesService(repos)
    applications = ApplicationsService(repos)
    analytics = AnalyticsService(repos)

    widest = settings.max_page_limit
    # Web screens use limit=100 for these tables; API consumers and the students
    # table use the default. The cache key includes the limit, so warm both.
    steps: list[tuple[str, Callable[[], object]]] = []
    for size in (settings.default_page_limit, widest):
        steps.extend(
            [
                ("colleges", lambda size=size: colleges.list(WARM_ACTOR, limit=size)),
                ("companies", lambda size=size: companies.list(WARM_ACTOR, limit=size)),
                ("batches", lambda size=size: batches.list(WARM_ACTOR, limit=size)),
                ("users", lambda size=size: users.list(WARM_ACTOR, limit=size)),
                ("applications", lambda size=size: applications.list(WARM_ACTOR, limit=size)),
            ]
        )
    steps.extend(
        [
            ("users/trainers", lambda: users.list(WARM_ACTOR, role="trainer", limit=widest)),
            ("students", lambda: students.list(WARM_ACTOR, limit=settings.default_page_limit)),
            (
                "students/at-risk",
                lambda: students.list(WARM_ACTOR, at_risk=True, limit=settings.default_page_limit),
            ),
            ("drives/dashboard", lambda: drives.list(WARM_ACTOR, limit=5)),
            ("drives", lambda: drives.list(WARM_ACTOR, limit=settings.default_page_limit)),
            ("analytics/placements", lambda: analytics.placements(WARM_ACTOR)),
        ]
    )
    return steps


def warm_caches(store: DocumentStore) -> None:
    """Best-effort warm-up; must never break startup or a request."""
    if not isinstance(store, FirestoreStore) or not store.cache_enabled:
        return
    repos = Repos(store)
    steps = _steps(repos)
    for label, step in steps:
        try:
            step()
        except Exception as exc:  # noqa: BLE001 - warming is optional
            logger.warning("Cache warm-up failed for %s: %s", label, exc)
    logger.info(
        "Cache warm-up finished", extra={"extra_fields": {"queries": len(steps)}}
    )
