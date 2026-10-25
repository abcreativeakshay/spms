"""Phase 4: interview feedback and internal-note visibility."""

from __future__ import annotations

from tests.helpers import setup_batch, setup_college, setup_drive, setup_student, today


def _setup(ctx):
    setup_college(ctx)
    setup_batch(ctx)
    setup_student(ctx)
    setup_student(ctx, "student-2", uid="uid-student-2")


def _payload(**overrides) -> dict:
    payload = {
        "studentId": "student-1",
        "interviewType": "mock",
        "date": today(),
        "ratings": {
            "technical": 4,
            "communication": 3,
            "problemSolving": 5,
            "attitude": 4,
        },
        "strengths": "Strong fundamentals",
        "improvements": "Explain trade-offs",
        "recommendation": "yes",
        "internalNotes": "Needs follow-up on system design",
    }
    payload.update(overrides)
    return payload


def test_trainer_creates_feedback_and_student_sees_redacted_copy(ctx):
    _setup(ctx)

    created = ctx.client.post(
        "/api/v1/feedback", headers=ctx.headers("trainer-1"), json=_payload()
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["averageRating"] == 4.0
    assert body["studentName"] == "Student student-1"
    assert body["internalNotes"] == "Needs follow-up on system design"

    trainer_view = ctx.client.get(
        "/api/v1/students/student-1/feedback", headers=ctx.headers("trainer-1")
    )
    assert trainer_view.status_code == 200
    assert trainer_view.json()[0]["internalNotes"] == "Needs follow-up on system design"

    student_view = ctx.client.get(
        "/api/v1/students/student-1/feedback", headers=ctx.headers("uid-student-1")
    )
    assert student_view.status_code == 200
    assert "internalNotes" not in student_view.json()[0]

    # Feedback raises the denormalized interview average on the student document.
    student = ctx.store.get("students", "student-1")
    assert student["interviewAvg"] == 80.0


def test_feedback_rejects_students_and_cross_batch_trainers(ctx):
    _setup(ctx)
    ctx.seed_user("trainer-2", "trainer", college_ids=["college-1"])

    as_student = ctx.client.post(
        "/api/v1/feedback", headers=ctx.headers("uid-student-1"), json=_payload()
    )
    assert as_student.status_code == 403
    assert as_student.json()["code"] == "role_forbidden"

    as_other_trainer = ctx.client.post(
        "/api/v1/feedback", headers=ctx.headers("trainer-2"), json=_payload()
    )
    assert as_other_trainer.status_code == 403
    assert as_other_trainer.json()["code"] == "batch_forbidden"


def test_feedback_validates_drive_and_ratings(ctx):
    _setup(ctx)
    setup_drive(ctx)

    bad_rating = ctx.client.post(
        "/api/v1/feedback",
        headers=ctx.headers("trainer-1"),
        json=_payload(
            ratings={
                "technical": 9,
                "communication": 3,
                "problemSolving": 3,
                "attitude": 3,
            }
        ),
    )
    assert bad_rating.status_code == 422

    missing_drive = ctx.client.post(
        "/api/v1/feedback",
        headers=ctx.headers("trainer-1"),
        json=_payload(driveId="drive-missing"),
    )
    assert missing_drive.status_code == 404
    assert missing_drive.json()["code"] == "drive_not_found"

    with_drive = ctx.client.post(
        "/api/v1/feedback",
        headers=ctx.headers("trainer-1"),
        json=_payload(driveId="drive-1", interviewType="real", recommendation="strong_yes"),
    )
    assert with_drive.status_code == 201, with_drive.text
    assert with_drive.json()["driveId"] == "drive-1"
    assert with_drive.json()["interviewType"] == "real"


def test_student_cannot_read_another_students_feedback(ctx):
    _setup(ctx)
    created = ctx.client.post(
        "/api/v1/feedback", headers=ctx.headers("trainer-1"), json=_payload()
    )
    assert created.status_code == 201

    forbidden = ctx.client.get(
        "/api/v1/students/student-1/feedback", headers=ctx.headers("uid-student-2")
    )
    assert forbidden.status_code == 403
    assert forbidden.json()["code"] == "student_forbidden"
