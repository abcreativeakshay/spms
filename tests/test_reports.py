"""Phase 5: CSV and PDF report exports."""

from __future__ import annotations

import csv
import io

from tests.helpers import setup_batch, setup_college, setup_drive, setup_student


def _setup(ctx):
    setup_college(ctx)
    setup_batch(ctx)
    setup_student(ctx)
    ctx.store.update(
        "students",
        "student-1",
        {
            "placementStatus": "placed",
            "placedCompany": "Acme",
            "placedCtc": 12.0,
        },
    )


def test_students_csv_export(ctx):
    _setup(ctx)
    response = ctx.client.get(
        "/api/v1/reports/export?report=students&format=csv",
        headers=ctx.headers("admin-1"),
    )
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/csv")
    assert "attachment; filename=" in response.headers["content-disposition"]
    assert "spms-students-" in response.headers["content-disposition"]

    rows = list(csv.DictReader(io.StringIO(response.text)))
    assert len(rows) == 1
    assert rows[0]["name"] == "Student student-1"
    assert rows[0]["college"] == "Test College"
    assert rows[0]["skills"] == "python;sql;react"


def test_placements_csv_and_pdf(ctx):
    _setup(ctx)
    csv_response = ctx.client.get(
        "/api/v1/reports/export?report=placements&format=csv&collegeId=college-1",
        headers=ctx.headers("admin-1"),
    )
    assert csv_response.status_code == 200
    rows = list(csv.DictReader(io.StringIO(csv_response.text)))
    assert rows[0]["placementStatus"] == "placed"
    assert rows[0]["company"] == "Acme"
    assert rows[0]["ctc"] == "12.0"

    pdf = ctx.client.get(
        "/api/v1/reports/export?report=placements&format=pdf",
        headers=ctx.headers("admin-1"),
    )
    assert pdf.status_code == 200, pdf.text
    assert pdf.headers["content-type"] == "application/pdf"
    assert pdf.content.startswith(b"%PDF")
    assert pdf.headers["content-disposition"].endswith('.pdf"')


def test_applications_attendance_and_drives_reports(ctx):
    _setup(ctx)
    setup_drive(ctx)
    ctx.store.set(
        "applications",
        "application-1",
        {
            "driveId": "drive-1",
            "studentId": "student-1",
            "studentName": "Student student-1",
            "collegeId": "college-1",
            "companyName": "Acme",
            "driveRole": "SDE",
            "status": "selected",
            "offer": {"ctc": 12.0},
            "appliedAt": "2026-01-01T00:00:00+00:00",
        },
    )
    ctx.store.set(
        "attendance",
        "attendance-1",
        {
            "sessionId": "session-1",
            "batchId": "batch-1",
            "studentId": "student-1",
            "sessionDate": "2026-01-05",
            "status": "present",
        },
    )

    applications = ctx.client.get(
        "/api/v1/reports/export?report=applications", headers=ctx.headers("admin-1")
    )
    assert applications.status_code == 200
    assert list(csv.DictReader(io.StringIO(applications.text)))[0]["company"] == "Acme"

    attendance = ctx.client.get(
        "/api/v1/reports/export?report=attendance", headers=ctx.headers("admin-1")
    )
    assert attendance.status_code == 200
    attendance_row = list(csv.DictReader(io.StringIO(attendance.text)))[0]
    assert attendance_row["present"] == "1"
    assert attendance_row["total"] == "1"

    drives = ctx.client.get(
        "/api/v1/reports/export?report=drives", headers=ctx.headers("admin-1")
    )
    assert drives.status_code == 200
    drive_row = list(csv.DictReader(io.StringIO(drives.text)))[0]
    assert drive_row["company"] == "Acme"
    assert drive_row["selected"] == "1"

    empty_batch = ctx.client.get(
        "/api/v1/reports/export?report=students&batchId=missing",
        headers=ctx.headers("admin-1"),
    )
    assert empty_batch.status_code == 200
    assert "No data" in empty_batch.text


def test_report_exports_are_admin_only_and_college_scoped(ctx):
    _setup(ctx)
    setup_college(ctx, "college-2", "Other College")
    ctx.seed_user(
        "admin-2",
        "admin",
        name="Other Admin",
        email="admin-2@spms.test",
        college_ids=["college-2"],
    )

    student = ctx.client.get(
        "/api/v1/reports/export?report=students", headers=ctx.headers("uid-student-1")
    )
    assert student.status_code == 403

    trainer = ctx.client.get(
        "/api/v1/reports/export?report=students", headers=ctx.headers("trainer-1")
    )
    assert trainer.status_code == 403

    other_college = ctx.client.get(
        "/api/v1/reports/export?report=students&collegeId=college-1",
        headers=ctx.headers("admin-2"),
    )
    assert other_college.status_code == 403
    assert other_college.json()["code"] == "college_scope_violation"

    scoped = ctx.client.get(
        "/api/v1/reports/export?report=students", headers=ctx.headers("admin-2")
    )
    assert scoped.status_code == 200
    assert "No data" in scoped.text
