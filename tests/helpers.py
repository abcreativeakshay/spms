"""Scenario builders shared by API tests."""

from __future__ import annotations

from datetime import date

from tests.conftest import Ctx


def setup_college(
    ctx: Ctx,
    college_id: str = "college-1",
    name: str = "Test College",
    *,
    super_admin_uid: str = "admin-1",
) -> tuple[str, str]:
    ctx.seed_college(college_id, name)
    ctx.seed_user(
        super_admin_uid,
        "admin",
        name="Super Admin",
        email=f"{super_admin_uid}@spms.test",
        college_ids=[college_id],
        super_admin=True,
    )
    return college_id, super_admin_uid


def setup_batch(
    ctx: Ctx,
    *,
    batch_id: str = "batch-1",
    college_id: str = "college-1",
    trainer_id: str = "trainer-1",
    min_attendance: float = 75.0,
) -> dict:
    ctx.seed_user(
        trainer_id,
        "trainer",
        name="Trainer One",
        email=f"{trainer_id}@spms.test",
        college_ids=[college_id],
    )
    return ctx.seed_batch(
        batch_id,
        college_id,
        trainerIds=[trainer_id],
        trainerNames=["Trainer One"],
        minAttendancePct=min_attendance,
    )


def setup_student(
    ctx: Ctx,
    student_id: str = "student-1",
    *,
    uid: str = "uid-student-1",
    college_id: str = "college-1",
    batch_id: str = "batch-1",
    **extra,
) -> dict:
    student = ctx.seed_student(
        student_id, uid=uid, college_id=college_id, batch_id=batch_id, **extra
    )
    ctx.seed_user(
        uid,
        "student",
        name=student["name"],
        email=student["email"],
        college_ids=[college_id],
    )
    return student


def setup_company(ctx: Ctx, company_id: str = "company-1", name: str = "Acme") -> dict:
    return ctx.store.set(
        "companies",
        company_id,
        {"name": name, "industry": "Software", "active": True},
    )


def setup_drive(
    ctx: Ctx,
    drive_id: str = "drive-1",
    *,
    company_id: str = "company-1",
    college_id: str = "college-1",
    **extra,
) -> dict:
    setup_company(ctx, company_id)
    return ctx.seed_drive(drive_id, company_id=company_id, collegeIds=[college_id], **extra)


def today() -> str:
    return date.today().isoformat()


def future(days: int = 30) -> str:
    from datetime import timedelta

    return (date.today() + timedelta(days=days)).isoformat()
