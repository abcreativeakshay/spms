"""Phase 5: student, batch, college and placement analytics."""

from __future__ import annotations

from tests.helpers import setup_batch, setup_college, setup_drive, setup_student, today


def _seed_activity(ctx) -> None:
    ctx.store.set(
        "sessions",
        "session-1",
        {"batchId": "batch-1", "date": "2026-01-05", "topic": "Python"},
    )
    ctx.store.set(
        "sessions",
        "session-2",
        {"batchId": "batch-1", "date": "2026-01-06", "topic": "SQL"},
    )
    ctx.store.set(
        "sessions",
        "session-3",
        {"batchId": "batch-1", "date": "2026-01-07", "topic": "React"},
    )
    for index, status in enumerate(("present", "absent", "late")):
        ctx.store.set(
            "attendance",
            f"attendance-{index}",
            {
                "sessionId": f"session-{index + 1}",
                "batchId": "batch-1",
                "studentId": "student-1",
                "sessionDate": f"2026-01-0{index + 5}",
                "status": status,
            },
        )
    ctx.store.set(
        "scores",
        "score-1",
        {
            "assessmentId": "assessment-1",
            "batchId": "batch-1",
            "studentId": "student-1",
            "marks": 80,
            "maxMarks": 100,
            "weightage": 1.0,
            "assessmentDate": "2026-01-07",
        },
    )


def _setup(ctx):
    setup_college(ctx)
    setup_batch(ctx)
    setup_student(ctx)
    setup_student(ctx, "student-2", uid="uid-student-2", cgpa=7.0)
    _seed_activity(ctx)


def test_student_analytics_trends_and_readiness(ctx):
    _setup(ctx)
    response = ctx.client.get(
        "/api/v1/analytics/student/student-1", headers=ctx.headers("uid-student-1")
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["attendancePct"] == 66.7
    assert body["assessmentAvg"] == 80.0
    assert body["interviewAvg"] == 0.0
    assert body["profileScore"] == 100
    # No interview feedback yet: interview weight is re-normalized away.
    assert "interview" not in body["readiness"]["weights"]
    assert body["readinessScore"] == 79.1
    assert [point["label"] for point in body["attendanceTrend"]] == [
        "2026-01-05",
        "2026-01-06",
        "2026-01-07",
    ]
    assert body["scoreTrend"][0]["value"] == 80.0
    assert body["rankBand"] == "top_10_percent"
    assert body["placementStatus"] == "unplaced"


def test_student_analytics_access_controls(ctx):
    _setup(ctx)
    own = ctx.client.get(
        "/api/v1/analytics/student/student-1", headers=ctx.headers("uid-student-1")
    )
    assert own.status_code == 200

    other = ctx.client.get(
        "/api/v1/analytics/student/student-1", headers=ctx.headers("uid-student-2")
    )
    assert other.status_code == 403

    trainer = ctx.client.get(
        "/api/v1/analytics/student/student-1", headers=ctx.headers("trainer-1")
    )
    assert trainer.status_code == 200

    missing = ctx.client.get(
        "/api/v1/analytics/student/nope", headers=ctx.headers("admin-1")
    )
    assert missing.status_code == 404


def test_batch_analytics_heatmap_distribution_and_risk(ctx):
    _setup(ctx)
    ctx.store.update(
        "students", "student-2", {"atRisk": True, "attendancePct": 40.0, "readinessScore": 50.0}
    )

    response = ctx.client.get(
        "/api/v1/analytics/batch/batch-1", headers=ctx.headers("trainer-1")
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["students"] == 2
    assert body["placementRate"] == 0.0
    assert body["atRisk"][0]["studentId"] == "student-2"
    assert len(body["attendanceHeatmap"]) == 3
    assert [row["percentage"] for row in body["attendanceHeatmap"]] == [100.0, 0.0, 100.0]
    assert sum(bucket["count"] for bucket in body["assessmentDistribution"]) == 1
    assert body["assessmentDistribution"][4]["count"] == 1
    assert body["topStudents"][0]["studentId"] == "student-1"

    student_attempt = ctx.client.get(
        "/api/v1/analytics/batch/batch-1", headers=ctx.headers("uid-student-1")
    )
    assert student_attempt.status_code == 403


def test_college_and_placement_analytics(ctx):
    _setup(ctx)
    ctx.store.update(
        "students",
        "student-1",
        {
            "placementStatus": "placed",
            "placedCompany": "Acme",
            "placedCtc": 12.0,
            "placementLocked": True,
        },
    )
    ctx.store.set(
        "applications",
        "application-1",
        {
            "driveId": "drive-1",
            "studentId": "student-1",
            "studentName": "Student student-1",
            "collegeId": "college-1",
            "companyId": "company-1",
            "companyName": "Acme",
            "driveRole": "SDE",
            "status": "selected",
            "offer": {"ctc": 12.0},
        },
    )
    setup_drive(ctx)

    college = ctx.client.get(
        "/api/v1/analytics/college/college-1", headers=ctx.headers("admin-1")
    )
    assert college.status_code == 200, college.text
    college_body = college.json()
    assert college_body["students"] == 2
    assert college_body["placed"] == 1
    assert college_body["placementRate"] == 50.0
    assert college_body["averagePackage"] == 12.0
    assert college_body["highestPackage"] == 12.0
    assert college_body["byBranch"][0]["branch"] == "CSE"
    assert college_body["byCompany"][0]["company"] == "Acme"

    placements = ctx.client.get("/api/v1/analytics/placements", headers=ctx.headers("admin-1"))
    assert placements.status_code == 200, placements.text
    body = placements.json()
    assert body["students"] == 2
    assert body["placed"] == 1
    assert body["medianPackage"] == 12.0
    # The placed + locked student is dream-offer ineligible, so only student-2 remains.
    assert body["funnel"]["eligible"] == 1
    assert body["funnel"]["applied"] == 1
    assert body["funnel"]["selected"] == 1
    assert body["funnel"]["conversionRates"]["selectedToShortlisted"] == 100.0

    trainer_forbidden = ctx.client.get(
        "/api/v1/analytics/placements", headers=ctx.headers("trainer-1")
    )
    assert trainer_forbidden.status_code == 403


def test_snapshots_are_created_and_reused(ctx):
    _setup(ctx)
    created = ctx.client.post(
        "/api/v1/analytics/student/student-1/snapshot", headers=ctx.headers("admin-1")
    )
    assert created.status_code == 201, created.text
    snapshot = created.json()
    assert snapshot["scope"] == "student"
    assert snapshot["scopeId"] == "student-1"
    assert snapshot["metrics"]["studentId"] == "student-1"
    snapshot_id = snapshot["id"]

    cached = ctx.client.get(
        "/api/v1/analytics/student/student-1?snapshot=true",
        headers=ctx.headers("uid-student-1"),
    )
    assert cached.status_code == 200
    assert cached.json()["studentId"] == "student-1"
    assert cached.json()["computedAt"] is not None

    # Re-snapshotting updates the same document instead of duplicating it.
    again = ctx.client.post(
        "/api/v1/analytics/student/student-1/snapshot", headers=ctx.headers("admin-1")
    )
    assert again.status_code == 201
    assert again.json()["id"] == snapshot_id
    assert ctx.store.count("analytics_snapshots") == 1

    invalid = ctx.client.post(
        "/api/v1/analytics/quiz/student-1/snapshot", headers=ctx.headers("admin-1")
    )
    assert invalid.status_code == 404
    assert invalid.json()["code"] == "invalid_scope"
