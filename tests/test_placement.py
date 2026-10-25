"""Phase 3: companies, drives, eligibility, applications and outcomes."""

from __future__ import annotations

from tests.helpers import (
    future,
    setup_batch,
    setup_college,
    setup_company,
    setup_drive,
    setup_student,
)


def _setup(ctx):
    setup_college(ctx)
    setup_batch(ctx)
    setup_student(ctx)
    setup_student(ctx, "student-2", uid="uid-student-2", cgpa=5.0)
    setup_company(ctx)


def _create_drive(ctx, **overrides) -> dict:
    payload = {
        "companyId": "company-1",
        "role": "SDE",
        "ctc": 12.0,
        "location": "Bengaluru",
        "driveDate": future(30),
        "deadline": future(15),
        "rounds": [{"name": "Aptitude"}, {"name": "Interview"}],
        "eligibility": {
            "minCgpa": 6.0,
            "minAttendance": 70,
            "minAssessmentAvg": 0,
        },
        "status": "open",
        "allowDreamOffer": False,
    }
    payload.update(overrides)
    response = ctx.client.post("/api/v1/drives", headers=ctx.headers("admin-1"), json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def test_create_drive_validates_dates_and_company(ctx):
    _setup(ctx)
    bad_dates = ctx.client.post(
        "/api/v1/drives",
        headers=ctx.headers("admin-1"),
        json={
            "companyId": "company-1",
            "role": "SDE",
            "ctc": 10,
            "driveDate": future(5),
            "deadline": future(10),
        },
    )
    assert bad_dates.status_code == 400
    assert bad_dates.json()["code"] == "invalid_date_range"

    missing_company = ctx.client.post(
        "/api/v1/drives",
        headers=ctx.headers("admin-1"),
        json={
            "companyId": "nope",
            "role": "SDE",
            "ctc": 10,
            "driveDate": future(10),
            "deadline": future(5),
        },
    )
    assert missing_company.status_code == 404


def test_eligibility_apply_and_reasons(ctx):
    _setup(ctx)
    ctx.seed_user("admin-root", "admin", college_ids=["*"], super_admin=True)
    drive = _create_drive(ctx)

    eligible = ctx.client.get("/api/v1/drives", headers=ctx.headers("uid-student-1"))
    assert eligible.status_code == 200
    item = next(d for d in eligible.json()["items"] if d["id"] == drive["id"])
    assert item["eligibilityResult"]["eligible"] is True
    assert item["application"] is None

    ineligible = ctx.client.get("/api/v1/drives", headers=ctx.headers("uid-student-2"))
    item2 = next(d for d in ineligible.json()["items"] if d["id"] == drive["id"])
    assert item2["eligibilityResult"]["eligible"] is False
    assert any("CGPA" in reason for reason in item2["eligibilityResult"]["reasons"])

    apply = ctx.client.post(
        f"/api/v1/drives/{drive['id']}/apply",
        headers=ctx.headers("uid-student-1"),
        json={"coverNote": "Excited"},
    )
    assert apply.status_code == 201, apply.text
    application_id = apply.json()["id"]

    drive_with_stats = ctx.client.get(
        f"/api/v1/drives/{drive['id']}", headers=ctx.headers("admin-1")
    )
    assert drive_with_stats.json()["stats"]["applied"] == 1

    # The student and every admin who can see the application are notified,
    # including super admins whose collegeIds are ["*"].
    student_notes = ctx.client.get(
        "/api/v1/notifications", headers=ctx.headers("uid-student-1")
    ).json()["items"]
    assert student_notes[0]["link"] == f"/applications/{application_id}"
    root_notes = ctx.client.get(
        "/api/v1/notifications", headers=ctx.headers("admin-root")
    ).json()["items"]
    assert root_notes[0]["link"] == f"/applications/{application_id}"

    duplicate = ctx.client.post(
        f"/api/v1/drives/{drive['id']}/apply", headers=ctx.headers("uid-student-1")
    )
    assert duplicate.status_code == 409

    blocked = ctx.client.post(
        f"/api/v1/drives/{drive['id']}/apply", headers=ctx.headers("uid-student-2")
    )
    assert blocked.status_code == 403
    assert blocked.json()["code"] == "not_eligible"

    eligible_students = ctx.client.get(
        f"/api/v1/drives/{drive['id']}/eligible-students", headers=ctx.headers("admin-1")
    )
    assert eligible_students.status_code == 200
    body = eligible_students.json()
    assert body["eligible"] == 1
    assert body["items"][0]["studentId"] == "student-1"
    assert body["items"][0]["applied"] is True

    mine = ctx.client.get(
        "/api/v1/applications", headers=ctx.headers("uid-student-1")
    ).json()
    assert [a["id"] for a in mine["items"]] == [application_id]


def test_rounds_outcome_and_placement(ctx):
    _setup(ctx)
    drive = _create_drive(ctx)
    application = ctx.client.post(
        f"/api/v1/drives/{drive['id']}/apply", headers=ctx.headers("uid-student-1")
    ).json()

    student_cannot_record = ctx.client.patch(
        f"/api/v1/applications/{application['id']}/round",
        headers=ctx.headers("uid-student-1"),
        json={"roundName": "Aptitude", "status": "cleared"},
    )
    assert student_cannot_record.status_code == 403

    unknown_round = ctx.client.patch(
        f"/api/v1/applications/{application['id']}/round",
        headers=ctx.headers("admin-1"),
        json={"roundName": "Magic", "status": "cleared"},
    )
    assert unknown_round.status_code == 400
    assert unknown_round.json()["code"] == "unknown_round"

    cleared = ctx.client.patch(
        f"/api/v1/applications/{application['id']}/round",
        headers=ctx.headers("admin-1"),
        json={"roundName": "Aptitude", "status": "cleared", "score": 88},
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["status"] == "in_process"
    assert cleared.json()["currentRound"] == "Aptitude"

    selected = ctx.client.patch(
        f"/api/v1/applications/{application['id']}/outcome",
        headers=ctx.headers("admin-1"),
        json={"outcome": "selected", "ctc": 15.5, "offerDate": future(2)},
    )
    assert selected.status_code == 200, selected.text
    assert selected.json()["status"] == "selected"
    assert selected.json()["offer"]["ctc"] == 15.5

    student = ctx.store.get("students", "student-1")
    assert student["placementStatus"] == "placed"
    assert student["placedCompany"] == "Acme"
    assert student["placementLocked"] is True

    drive_after = ctx.client.get(f"/api/v1/drives/{drive['id']}", headers=ctx.headers("admin-1"))
    assert drive_after.json()["stats"]["selected"] == 1

    offer = ctx.client.post(
        f"/api/v1/applications/{application['id']}/offer-letter",
        headers=ctx.headers("admin-1"),
        files={"file": ("offer.pdf", b"%PDF-1.4 offer", "application/pdf")},
    )
    assert offer.status_code == 200, offer.text
    assert offer.json()["offerLetterUrl"].startswith("local://storage/")

    url = ctx.client.get(
        f"/api/v1/applications/{application['id']}/offer-letter-url",
        headers=ctx.headers("uid-student-1"),
    )
    assert url.status_code == 200


def test_dream_offer_requires_override(ctx):
    _setup(ctx)
    first = _create_drive(ctx, role="SDE")
    application = ctx.client.post(
        f"/api/v1/drives/{first['id']}/apply", headers=ctx.headers("uid-student-1")
    ).json()
    ctx.client.patch(
        f"/api/v1/applications/{application['id']}/outcome",
        headers=ctx.headers("admin-1"),
        json={"outcome": "selected", "ctc": 12},
    )

    dream = _create_drive(
        ctx, role="Dream SDE", ctc=30, allowDreamOffer=True, deadline=future(20), driveDate=future(40)
    )
    locked = ctx.client.post(
        f"/api/v1/drives/{dream['id']}/apply", headers=ctx.headers("uid-student-1")
    )
    assert locked.status_code == 403
    assert any(
        "dream" in reason.lower() for reason in locked.json()["details"]["reasons"]
    )

    override = ctx.client.patch(
        "/api/v1/students/student-1",
        headers=ctx.headers("admin-1"),
        json={"placementLocked": False},
    )
    assert override.status_code == 200
    allowed = ctx.client.post(
        f"/api/v1/drives/{dream['id']}/apply", headers=ctx.headers("uid-student-1")
    )
    assert allowed.status_code == 201, allowed.text


def test_withdraw_reverts_placement(ctx):
    _setup(ctx)
    drive = _create_drive(ctx)
    application = ctx.client.post(
        f"/api/v1/drives/{drive['id']}/apply", headers=ctx.headers("uid-student-1")
    ).json()
    ctx.client.patch(
        f"/api/v1/applications/{application['id']}/outcome",
        headers=ctx.headers("admin-1"),
        json={"outcome": "selected", "ctc": 12},
    )

    withdrawn = ctx.client.patch(
        f"/api/v1/applications/{application['id']}/outcome",
        headers=ctx.headers("uid-student-1"),
        json={"outcome": "withdrawn"},
    )
    assert withdrawn.status_code == 200, withdrawn.text
    assert ctx.store.get("students", "student-1")["placementStatus"] == "unplaced"


def test_closed_deadline_blocks_application(ctx):
    _setup(ctx)
    drive = setup_drive(ctx, deadline="2020-01-01", driveDate="2020-02-01")
    response = ctx.client.post(
        f"/api/v1/drives/{drive['id']}/apply", headers=ctx.headers("uid-student-1")
    )
    assert response.status_code == 409
    assert response.json()["code"] == "drive_closed"
