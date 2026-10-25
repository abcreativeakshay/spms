"""Phase 4: notifications, ownership checks and the audit trail."""

from __future__ import annotations

from app.models.enums import NotificationType
from app.repositories import Repos
from app.services.notify import NotificationService
from tests.helpers import setup_batch, setup_college, setup_student, today


def _setup(ctx):
    setup_college(ctx)
    setup_batch(ctx)
    setup_student(ctx)
    setup_student(ctx, "student-2", uid="uid-student-2")


def _feedback(ctx) -> dict:
    response = ctx.client.post(
        "/api/v1/feedback",
        headers=ctx.headers("trainer-1"),
        json={
            "studentId": "student-1",
            "interviewType": "mock",
            "date": today(),
            "ratings": {
                "technical": 4,
                "communication": 4,
                "problemSolving": 4,
                "attitude": 4,
            },
            "recommendation": "yes",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_feedback_notifies_student_and_marks_read(ctx):
    _setup(ctx)
    _feedback(ctx)

    listing = ctx.client.get("/api/v1/notifications", headers=ctx.headers("uid-student-1"))
    assert listing.status_code == 200
    body = listing.json()
    assert len(body["items"]) == 1
    notification = body["items"][0]
    assert notification["type"] == "feedback"
    assert notification["read"] is False
    assert notification["userId"] == "uid-student-1"

    unread = ctx.client.get(
        "/api/v1/notifications?unreadOnly=true", headers=ctx.headers("uid-student-1")
    )
    assert len(unread.json()["items"]) == 1

    marked = ctx.client.patch(
        f"/api/v1/notifications/{notification['id']}/read",
        headers=ctx.headers("uid-student-1"),
    )
    assert marked.status_code == 200
    assert marked.json()["read"] is True

    unread_after = ctx.client.get(
        "/api/v1/notifications?unreadOnly=true", headers=ctx.headers("uid-student-1")
    )
    assert unread_after.json()["items"] == []

    # Other students never see someone else's inbox.
    other = ctx.client.get("/api/v1/notifications", headers=ctx.headers("uid-student-2"))
    assert other.json()["items"] == []


def test_notification_ownership_and_read_all(ctx):
    _setup(ctx)
    for note_id, title in (("note-1", "Hello"), ("note-2", "Second")):
        ctx.store.set(
            "notifications",
            note_id,
            {
                "userId": "uid-student-1",
                "type": "system",
                "title": title,
                "body": "Body",
                "read": False,
            },
        )

    forbidden = ctx.client.patch(
        "/api/v1/notifications/note-1/read", headers=ctx.headers("uid-student-2")
    )
    assert forbidden.status_code == 403
    assert forbidden.json()["code"] == "notification_forbidden"

    missing = ctx.client.patch(
        "/api/v1/notifications/does-not-exist/read", headers=ctx.headers("uid-student-1")
    )
    assert missing.status_code == 404

    read_all = ctx.client.patch(
        "/api/v1/notifications/read-all", headers=ctx.headers("uid-student-1")
    )
    assert read_all.status_code == 200
    assert ctx.store.get("notifications", "note-1")["read"] is True
    assert ctx.store.get("notifications", "note-2")["read"] is True


def test_mutations_write_scoped_audit_logs(ctx):
    _setup(ctx)
    feedback = _feedback(ctx)

    logs = ctx.client.get("/api/v1/audit-logs", headers=ctx.headers("admin-1"))
    assert logs.status_code == 200, logs.text
    entries = logs.json()["items"]
    entry = next(e for e in entries if e["action"] == "feedback.create")
    assert entry["actorId"] == "trainer-1"
    assert entry["entity"] == "feedback"
    assert entry["entityId"] == feedback["id"]
    assert entry["collegeId"] == "college-1"

    filtered = ctx.client.get(
        "/api/v1/audit-logs?entity=feedback", headers=ctx.headers("admin-1")
    )
    assert all(e["entity"] == "feedback" for e in filtered.json()["items"])

    # Trainers and students cannot read the audit trail.
    assert (
        ctx.client.get("/api/v1/audit-logs", headers=ctx.headers("trainer-1")).status_code == 403
    )
    assert (
        ctx.client.get("/api/v1/audit-logs", headers=ctx.headers("uid-student-1")).status_code
        == 403
    )


def test_audit_logs_are_college_scoped(ctx):
    _setup(ctx)
    _feedback(ctx)
    setup_college(ctx, "college-2", "Other College")
    ctx.seed_user(
        "admin-2",
        "admin",
        name="Other Admin",
        email="admin-2@spms.test",
        college_ids=["college-2"],
    )

    other_admin = ctx.client.get("/api/v1/audit-logs", headers=ctx.headers("admin-2"))
    assert other_admin.status_code == 200
    assert other_admin.json()["items"] == []

    super_admin = ctx.client.get("/api/v1/audit-logs", headers=ctx.headers("admin-1"))
    assert any(e["action"] == "feedback.create" for e in super_admin.json()["items"])


def test_notification_email_queue(ctx):
    _setup(ctx)
    service = NotificationService(Repos(ctx.store))
    created = service.notify(
        ["uid-student-1"],
        notification_type=NotificationType.SYSTEM,
        title="Queued",
        body="Also emailed",
        email=True,
    )
    assert created == 1
    mail = ctx.store.query("mail")
    assert len(mail) == 1
    assert mail[0]["to"] == ["student-1@spms.test"]
