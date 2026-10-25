"""Phase 2: attendance sessions, marking, corrections, summaries."""

from __future__ import annotations

from datetime import date, timedelta

from tests.helpers import setup_batch, setup_college, setup_student, today


def _setup(ctx, min_attendance: float = 75.0):
    setup_college(ctx)
    setup_batch(ctx, min_attendance=min_attendance)
    setup_student(ctx)
    setup_student(ctx, "student-2", uid="uid-student-2")


def _session(ctx, trainer="trainer-1", date_value: str | None = None) -> dict:
    response = ctx.client.post(
        "/api/v1/batches/batch-1/sessions",
        headers=ctx.headers(trainer),
        json={"date": date_value or today(), "topic": "Arrays"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_mark_attendance_and_student_view(ctx):
    _setup(ctx)
    session = _session(ctx)

    marked = ctx.client.post(
        f"/api/v1/sessions/{session['id']}/attendance",
        headers=ctx.headers("trainer-1"),
        json={
            "records": [
                {"studentId": "student-1", "status": "present"},
                {"studentId": "student-2", "status": "absent"},
            ]
        },
    )
    assert marked.status_code == 200, marked.text
    assert marked.json()["present"] == 1
    assert marked.json()["total"] == 2

    view = ctx.client.get(
        "/api/v1/students/student-1/attendance", headers=ctx.headers("uid-student-1")
    )
    assert view.status_code == 200
    body = view.json()
    assert body["percentage"] == 100.0
    assert body["total"] == 1
    assert body["history"][0]["topic"] == "Arrays"

    summary = ctx.client.get(
        "/api/v1/batches/batch-1/attendance/summary", headers=ctx.headers("trainer-1")
    )
    assert summary.status_code == 200
    assert summary.json()["averagePercentage"] == 50.0
    assert summary.json()["atRiskCount"] == 1
    assert len(summary.json()["heatmap"]) == 1


def test_low_attendance_triggers_notification(ctx):
    _setup(ctx)
    session = _session(ctx)
    ctx.client.post(
        f"/api/v1/sessions/{session['id']}/attendance",
        headers=ctx.headers("trainer-1"),
        json={"records": [{"studentId": "student-1", "status": "absent"}]},
    )
    student = ctx.store.get("students", "student-1")
    assert student["attendancePct"] == 0.0
    assert student["atRisk"] is True

    notes = ctx.client.get("/api/v1/notifications", headers=ctx.headers("uid-student-1")).json()
    assert any(note["type"] == "attendance" for note in notes["items"])


def test_correction_is_audited_and_window_enforced(ctx):
    _setup(ctx)
    session = _session(ctx)
    marked = ctx.client.post(
        f"/api/v1/sessions/{session['id']}/attendance",
        headers=ctx.headers("trainer-1"),
        json={"records": [{"studentId": "student-1", "status": "absent"}]},
    )
    attendance_id = f"{session['id']}_student-1"

    corrected = ctx.client.patch(
        f"/api/v1/attendance/{attendance_id}",
        headers=ctx.headers("trainer-1"),
        json={"status": "present", "reason": "Was present, marked by mistake"},
    )
    assert corrected.status_code == 200, corrected.text
    assert corrected.json()["status"] == "present"

    student = ctx.store.get("students", "student-1")
    assert student["attendancePct"] == 100.0

    logs = ctx.client.get("/api/v1/audit-logs?entity=attendance", headers=ctx.headers("admin-1"))
    assert logs.status_code == 200
    assert any(log["action"] == "attendance.correct" for log in logs.json()["items"])
    # Attendance documents denormalize the batch, not the college; the audit log
    # must still be visible to a college admin.
    assert all(log["collegeId"] == "college-1" for log in logs.json()["items"])

    old_date = (date.today() - timedelta(days=30)).isoformat()
    old_session = _session(ctx, date_value=old_date)
    ctx.client.post(
        f"/api/v1/sessions/{old_session['id']}/attendance",
        headers=ctx.headers("trainer-1"),
        json={"records": [{"studentId": "student-1", "status": "absent"}]},
    )
    expired = ctx.client.patch(
        f"/api/v1/attendance/{old_session['id']}_student-1",
        headers=ctx.headers("trainer-1"),
        json={"status": "present", "reason": "Too late"},
    )
    assert expired.status_code == 403
    assert expired.json()["code"] == "correction_window_expired"


def test_other_trainer_cannot_mark(ctx):
    _setup(ctx)
    session = _session(ctx)
    ctx.seed_user("trainer-x", "trainer", college_ids=["college-1"])
    response = ctx.client.post(
        f"/api/v1/sessions/{session['id']}/attendance",
        headers=ctx.headers("trainer-x"),
        json={"records": [{"studentId": "student-1", "status": "present"}]},
    )
    assert response.status_code == 403
    assert response.json()["code"] == "batch_forbidden"


def test_student_cannot_mark_attendance(ctx):
    _setup(ctx)
    session = _session(ctx)
    response = ctx.client.post(
        f"/api/v1/sessions/{session['id']}/attendance",
        headers=ctx.headers("uid-student-1"),
        json={"records": [{"studentId": "student-1", "status": "present"}]},
    )
    assert response.status_code == 403
