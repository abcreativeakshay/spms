"""Phase 2: assessments, bulk scores, student rank bands."""

from __future__ import annotations

from tests.helpers import setup_batch, setup_college, setup_student, today


def _setup(ctx):
    setup_college(ctx)
    setup_batch(ctx)
    setup_student(ctx)
    setup_student(ctx, "student-2", uid="uid-student-2")


def _assessment(ctx, max_marks: float = 100) -> dict:
    response = ctx.client.post(
        "/api/v1/assessments",
        headers=ctx.headers("trainer-1"),
        json={
            "batchId": "batch-1",
            "title": "DSA Quiz 1",
            "type": "quiz",
            "maxMarks": max_marks,
            "weightage": 1,
            "date": today(),
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_score_entry_and_student_view(ctx):
    _setup(ctx)
    assessment = _assessment(ctx)

    saved = ctx.client.post(
        f"/api/v1/assessments/{assessment['id']}/scores",
        headers=ctx.headers("trainer-1"),
        json={
            "records": [
                {"studentId": "student-1", "marks": 90, "remarks": "Great"},
                {"studentId": "student-2", "marks": 50},
            ]
        },
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["saved"] == 2

    view = ctx.client.get(
        "/api/v1/students/student-1/scores", headers=ctx.headers("uid-student-1")
    )
    assert view.status_code == 200
    body = view.json()
    assert body["overallAverage"] == 90.0
    assert body["items"][0]["classAverage"] == 70.0
    assert body["items"][0]["rankBand"] == "top_10_percent"
    assert body["items"][0]["marks"] == 90

    student = ctx.store.get("students", "student-1")
    assert student["assessmentAvg"] == 90.0

    analytics = ctx.client.get(
        f"/api/v1/assessments/{assessment['id']}/analytics", headers=ctx.headers("trainer-1")
    )
    assert analytics.status_code == 200
    assert analytics.json()["average"] == 70.0
    assert sum(bucket["count"] for bucket in analytics.json()["distribution"]) == 2


def test_score_validation_and_permissions(ctx):
    _setup(ctx)
    assessment = _assessment(ctx, max_marks=50)

    too_high = ctx.client.post(
        f"/api/v1/assessments/{assessment['id']}/scores",
        headers=ctx.headers("trainer-1"),
        json={"records": [{"studentId": "student-1", "marks": 80}]},
    )
    assert too_high.status_code == 400
    assert too_high.json()["code"] == "invalid_marks"

    other_student = ctx.client.get(
        "/api/v1/students/student-2/scores", headers=ctx.headers("uid-student-1")
    )
    assert other_student.status_code == 403

    student_cannot_list_scores = ctx.client.get(
        f"/api/v1/assessments/{assessment['id']}/scores",
        headers=ctx.headers("uid-student-1"),
    )
    assert student_cannot_list_scores.status_code == 403

    other_trainer = ctx.headers("trainer-x")
    ctx.seed_user("trainer-x", "trainer", college_ids=["college-1"])
    denied = ctx.client.post(
        f"/api/v1/assessments/{assessment['id']}/scores",
        headers=other_trainer,
        json={"records": [{"studentId": "student-1", "marks": 10}]},
    )
    assert denied.status_code == 403


def test_score_csv_import(ctx):
    _setup(ctx)
    assessment = _assessment(ctx)
    csv_data = "studentId,marks,remarks\nstudent-1,75,ok\nghost,10,\nstudent-2,notanumber,\n"
    response = ctx.client.post(
        f"/api/v1/assessments/{assessment['id']}/scores/import",
        headers=ctx.headers("trainer-1"),
        files={"file": ("scores.csv", csv_data, "text/csv")},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["saved"] == 1
    assert len(body["errors"]) == 2


def test_student_sees_only_own_scores(ctx):
    _setup(ctx)
    assessment = _assessment(ctx)
    ctx.client.post(
        f"/api/v1/assessments/{assessment['id']}/scores",
        headers=ctx.headers("trainer-1"),
        json={"records": [{"studentId": "student-2", "marks": 95}]},
    )
    own = ctx.client.get(
        "/api/v1/students/student-1/scores", headers=ctx.headers("uid-student-1")
    )
    assert own.status_code == 200
    assert own.json()["items"] == []
