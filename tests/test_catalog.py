"""Phase 1: colleges, batches, assignments and the company catalogue."""

from __future__ import annotations

from tests.helpers import setup_batch, setup_college, setup_drive, setup_student


def _admin_headers(ctx, uid: str = "admin-1") -> dict[str, str]:
    return ctx.headers(uid)


# -- colleges --------------------------------------------------------------- #
def test_college_crud_and_rename_propagation(ctx):
    setup_college(ctx)
    setup_batch(ctx)
    setup_student(ctx)

    limited = ctx.client.post(
        "/api/v1/colleges",
        headers=_admin_headers(ctx, "admin-limited"),
        json={"name": "Nope"},
    )
    assert limited.status_code == 403  # unknown user is not provisioned

    ctx.seed_user("admin-limited", "admin", college_ids=["college-1"])
    limited = ctx.client.post(
        "/api/v1/colleges",
        headers=_admin_headers(ctx, "admin-limited"),
        json={"name": "Nope"},
    )
    assert limited.status_code == 403
    assert limited.json()["code"] == "super_admin_required"

    created = ctx.client.post(
        "/api/v1/colleges",
        headers=_admin_headers(ctx),
        json={"name": "Second College", "city": "Mumbai", "contactEmail": "dean@spms.test"},
    )
    assert created.status_code == 201, created.text
    college_id = created.json()["id"]

    fetched = ctx.client.get(f"/api/v1/colleges/{college_id}", headers=_admin_headers(ctx))
    assert fetched.status_code == 200
    assert fetched.json()["studentCount"] == 0
    assert fetched.json()["batchCount"] == 0

    renamed = ctx.client.patch(
        f"/api/v1/colleges/college-1",
        headers=_admin_headers(ctx),
        json={"name": "Renamed College"},
    )
    assert renamed.status_code == 200, renamed.text
    assert ctx.store.get("batches", "batch-1")["collegeName"] == "Renamed College"
    assert ctx.store.get("students", "student-1")["collegeName"] == "Renamed College"

    listed = ctx.client.get("/api/v1/colleges?q=Renamed", headers=_admin_headers(ctx))
    assert [c["id"] for c in listed.json()["items"]] == ["college-1"]
    assert listed.json()["items"][0]["studentCount"] == 1
    assert listed.json()["items"][0]["batchCount"] == 1

    deactivated = ctx.client.delete(
        "/api/v1/colleges/college-1", headers=_admin_headers(ctx)
    )
    assert deactivated.status_code == 200
    assert deactivated.json()["active"] is False

    active_only = ctx.client.get("/api/v1/colleges?active=true", headers=_admin_headers(ctx))
    assert "college-1" not in [c["id"] for c in active_only.json()["items"]]

    other_admin = ctx.client.get(
        "/api/v1/colleges/college-1", headers=_admin_headers(ctx, "admin-limited")
    )
    assert other_admin.status_code == 200  # scoped admin can read their own college

    missing = ctx.client.get("/api/v1/colleges/missing", headers=_admin_headers(ctx))
    assert missing.status_code == 404


# -- batches ---------------------------------------------------------------- #
def _batch_payload(**overrides) -> dict:
    payload = {
        "name": "Batch New",
        "course": "Data Engineering",
        "collegeId": "college-1",
        "trainerIds": ["trainer-1"],
        "startDate": "2026-02-01",
        "endDate": "2026-07-31",
        "minAttendancePct": 80,
    }
    payload.update(overrides)
    return payload


def test_batch_create_validation_and_scoping(ctx):
    setup_college(ctx)
    ctx.seed_user("trainer-1", "trainer", college_ids=["college-1"])
    ctx.seed_user("trainer-2", "trainer", college_ids=["college-2"])

    bad_dates = ctx.client.post(
        "/api/v1/batches",
        headers=_admin_headers(ctx),
        json=_batch_payload(startDate="2026-08-01", endDate="2026-07-01"),
    )
    assert bad_dates.status_code == 400
    assert bad_dates.json()["code"] == "invalid_date_range"

    missing_college = ctx.client.post(
        "/api/v1/batches",
        headers=_admin_headers(ctx),
        json=_batch_payload(collegeId="college-9"),
    )
    assert missing_college.status_code == 400

    wrong_trainer = ctx.client.post(
        "/api/v1/batches",
        headers=_admin_headers(ctx),
        json=_batch_payload(trainerIds=["trainer-2"]),
    )
    assert wrong_trainer.status_code == 400
    assert wrong_trainer.json()["code"] == "trainer_college_mismatch"

    created = ctx.client.post(
        "/api/v1/batches", headers=_admin_headers(ctx), json=_batch_payload()
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["trainerNames"] == ["Trainer trainer-1"]
    assert body["collegeName"] == "Test College"
    assert body["studentCount"] == 0

    listed = ctx.client.get(
        "/api/v1/batches?collegeId=college-1", headers=ctx.headers("trainer-1")
    )
    assert listed.status_code == 200
    assert [b["id"] for b in listed.json()["items"]] == [body["id"]]

    trainer_other = ctx.client.get("/api/v1/batches", headers=ctx.headers("trainer-2"))
    assert trainer_other.json()["items"] == []


def test_batch_student_movement_and_updates(ctx):
    setup_college(ctx)
    setup_batch(ctx)
    ctx.seed_user("trainer-1", "trainer", college_ids=["college-1"])
    target = ctx.client.post(
        "/api/v1/batches", headers=_admin_headers(ctx), json=_batch_payload()
    ).json()
    setup_student(ctx, batch_id="batch-1")
    setup_student(ctx, "student-2", uid="uid-student-2", batch_id=None)

    assigned = ctx.client.post(
        f"/api/v1/batches/{target['id']}/students",
        headers=ctx.headers("trainer-1"),
        json={"studentIds": ["student-1", "student-2"]},
    )
    assert assigned.status_code == 200, assigned.text
    assert assigned.json()["assigned"] == 2
    assert len(assigned.json()["historyIds"]) == 2
    assert ctx.store.get("students", "student-1")["batchId"] == target["id"]
    assert ctx.store.get("students", "student-2")["batchId"] == target["id"]
    assert ctx.store.get("batches", target["id"])["studentCount"] == 2
    assert ctx.store.count("batchAssignments") == 2

    renamed = ctx.client.patch(
        f"/api/v1/batches/{target['id']}",
        headers=_admin_headers(ctx),
        json={"name": "Renamed Batch"},
    )
    assert renamed.status_code == 200
    assert ctx.store.get("students", "student-1")["batchName"] == "Renamed Batch"

    # Lowering the threshold flips an at-risk student (with attendance) back to safe.
    ctx.store.set(
        "attendance",
        "attendance-1",
        {"sessionId": "session-1", "batchId": target["id"], "studentId": "student-1", "status": "absent"},
    )
    ctx.store.update("students", "student-1", {"attendancePct": 50.0})
    relaxed = ctx.client.patch(
        f"/api/v1/batches/{target['id']}",
        headers=_admin_headers(ctx),
        json={"minAttendancePct": 40},
    )
    assert relaxed.status_code == 200
    assert ctx.store.get("students", "student-1")["atRisk"] is False

    archived = ctx.client.delete(
        f"/api/v1/batches/{target['id']}", headers=_admin_headers(ctx)
    )
    assert archived.status_code == 200
    assert archived.json()["status"] == "archived"

    own_batch = ctx.client.get("/api/v1/batches", headers=ctx.headers("uid-student-1"))
    assert [b["id"] for b in own_batch.json()["items"]] == [target["id"]]

    students = ctx.client.get(
        f"/api/v1/batches/{target['id']}/students", headers=ctx.headers("trainer-1")
    )
    assert students.status_code == 200
    assert {s["id"] for s in students.json()["items"]} == {"student-1", "student-2"}


def test_batch_assign_rejects_cross_college_and_missing(ctx):
    setup_college(ctx)
    setup_batch(ctx)
    setup_student(ctx, college_id="college-2")
    target = ctx.store.get("batches", "batch-1")

    mismatch = ctx.client.post(
        f"/api/v1/batches/{target['id']}/students",
        headers=_admin_headers(ctx),
        json={"studentIds": ["student-1"]},
    )
    assert mismatch.status_code == 400
    assert mismatch.json()["code"] == "college_mismatch"

    missing = ctx.client.post(
        f"/api/v1/batches/{target['id']}/students",
        headers=_admin_headers(ctx),
        json={"studentIds": ["ghost"]},
    )
    assert missing.status_code == 404

    student_attempt = ctx.client.post(
        f"/api/v1/batches/{target['id']}/students",
        headers=ctx.headers("uid-student-1"),
        json={"studentIds": ["student-1"]},
    )
    assert student_attempt.status_code == 403


# -- companies -------------------------------------------------------------- #
def test_company_crud_and_drive_rename(ctx):
    setup_college(ctx)
    setup_drive(ctx)  # creates company-1 and drive-1

    trainer_forbidden = ctx.client.post(
        "/api/v1/companies", headers=ctx.headers("trainer-1"), json={"name": "Nope Inc"}
    )
    assert trainer_forbidden.status_code == 403  # unprovisioned trainer
    ctx.seed_user("trainer-1", "trainer", college_ids=["college-1"])
    trainer_forbidden = ctx.client.post(
        "/api/v1/companies", headers=ctx.headers("trainer-1"), json={"name": "Nope Inc"}
    )
    assert trainer_forbidden.status_code == 403
    assert trainer_forbidden.json()["code"] == "role_forbidden"

    created = ctx.client.post(
        "/api/v1/companies",
        headers=_admin_headers(ctx),
        json={"name": "Globex", "industry": "Finance"},
    )
    assert created.status_code == 201, created.text
    company_id = created.json()["id"]

    fetched = ctx.client.get(f"/api/v1/companies/{company_id}", headers=_admin_headers(ctx))
    assert fetched.status_code == 200

    renamed = ctx.client.patch(
        "/api/v1/companies/company-1",
        headers=_admin_headers(ctx),
        json={"name": "Acme Corp"},
    )
    assert renamed.status_code == 200
    assert ctx.store.get("drives", "drive-1")["companyName"] == "Acme Corp"

    listed = ctx.client.get("/api/v1/companies?q=Globex", headers=_admin_headers(ctx))
    assert [c["id"] for c in listed.json()["items"]] == [company_id]

    linked = ctx.client.get("/api/v1/companies?q=Acme", headers=_admin_headers(ctx))
    assert linked.json()["items"][0]["driveCount"] == 1

    deactivated = ctx.client.delete(
        "/api/v1/companies/company-1", headers=_admin_headers(ctx)
    )
    assert deactivated.status_code == 200
    assert deactivated.json()["active"] is False

    active = ctx.client.get("/api/v1/companies?active=true", headers=_admin_headers(ctx))
    assert "company-1" not in [c["id"] for c in active.json()["items"]]

    missing = ctx.client.get("/api/v1/companies/nope", headers=_admin_headers(ctx))
    assert missing.status_code == 404
