"""SPMS — FastAPI application entrypoint."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.errors import register_exception_handlers
from app.core.logging import RequestContextMiddleware, configure_logging
from app.routers import (
    analytics,
    applications,
    assessments,
    attendance,
    auth,
    batches,
    colleges,
    companies,
    drives,
    feedback,
    notifications,
    reports,
    students,
    users,
)

logger = logging.getLogger("spms")

TAGS_METADATA = [
    {"name": "auth", "description": "Firebase session, current user, token revocation"},
    {"name": "users", "description": "Admin user management and CSV onboarding"},
    {"name": "colleges", "description": "Colleges (tenant scoping unit)"},
    {"name": "batches", "description": "Batches, trainers and student movement"},
    {"name": "students", "description": "Student profiles, search, resumes and import"},
    {"name": "attendance", "description": "Sessions, marking, corrections and summaries"},
    {"name": "assessments", "description": "Assessments, scores and student rank bands"},
    {"name": "companies", "description": "Company catalogue"},
    {"name": "drives", "description": "Placement drives and eligibility"},
    {"name": "applications", "description": "Applications, rounds, offers"},
    {"name": "feedback", "description": "Interview feedback"},
    {"name": "analytics", "description": "Dashboards, readiness and snapshots"},
    {"name": "reports", "description": "CSV and PDF exports"},
    {"name": "notifications", "description": "In-app notifications and audit log"},
]


@asynccontextmanager
async def lifespan(_: FastAPI):
    configure_logging(settings.debug)
    if settings.use_firebase:
        from app.core.firebase import init_firebase

        init_firebase()
        logger.info("Firebase initialized", extra={"extra_fields": {"project": settings.firebase_project_id}})
        if settings.firestore_warm_cache:
            import threading

            from app.core.warm import warm_caches
            from app.repositories.store import get_store

            threading.Thread(
                target=warm_caches,
                args=(get_store(),),
                name="spms-cache-warm",
                daemon=True,
            ).start()
    else:
        logger.warning(
            "Running with the in-memory store. Set USE_FIREBASE=true for Firestore.",
            extra={"extra_fields": {"env": settings.env}},
        )
        if settings.seed_demo:
            from app.core.demo import seed_demo_data
            from app.repositories.store import get_store

            seed_demo_data(get_store())
            logger.warning(
                "Seeded in-memory demo data (sign in with dev:demo-admin, dev:demo-trainer, "
                "dev:demo-student-1 or dev:demo-student-2)."
            )
    yield


app = FastAPI(
    title="SPMS API",
    description=(
        "Student Placement Management System. Authenticate with a Firebase ID token "
        "(`Authorization: Bearer <token>`). Errors use `{code, message, details}`."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    openapi_tags=TAGS_METADATA,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["x-request-id", "content-disposition"],
)
app.add_middleware(RequestContextMiddleware)

register_exception_handlers(app)

api = APIRouter(prefix=settings.api_prefix)
for module in (
    auth,
    users,
    colleges,
    batches,
    students,
    attendance,
    assessments,
    companies,
    drives,
    applications,
    feedback,
    analytics,
    reports,
    notifications,
):
    api.include_router(module.router)
app.include_router(api)


@app.get("/health", tags=["system"])
def health() -> dict:
    return {
        "status": "ok",
        "service": settings.app_name,
        "version": app.version,
        "store": "firestore" if settings.use_firebase else "memory",
    }


@app.get("/", include_in_schema=False)
def root() -> dict:
    return {
        "service": "SPMS API",
        "version": app.version,
        "docs": "/docs",
        "api": settings.api_prefix,
    }
