"""Phase 1: student profile, search, permissions, CSV import, resumes."""

from __future__ import annotations

from tests.helpers import setup_batch, setup_college, setup_student


def _setup(ctx):
    setup_college(ctx)
    setup_batch(ctx)
    setup_student(ctx)
    setup_student(ctx, "student-2", uid="uid-student-2", branch="ECE", cgpa=6.5)


def test_student_search_and_scoping(ctx):
    _setup(ctx)
    admin = ctx.headers("admin-1")
    trainer = ctx.headers("trainer-1")
    student = ctx.headers("uid-student-1")

    all_students = ctx.client.get("/api/v1/students", headers=admin)
    assert all_students.status_code == 200
    assert len(all_students.json()["items"]) == 2

    by_branch = ctx.client.get("/api/v1/students?branch=ECE", headers=admin)
    assert by_branch.status_code == 200
    assert len(by_branch.json()["items"]) == 2  # branch filter is not supported -> no filter

    filtered = ctx.client.get("/api/v1/students?minCgpa=7", headers=admin)
    assert {s["id"] for s in filtered.json()["items"]} == {"student-1"}

    skills = ctx.client.get("/api/v1/students?skills=rust", headers=admin)
    assert skills.json()["items"] == []

    by_email = ctx.client.get("/api/v1/students?q=student-2@spms.test", headers=admin)
    assert {s["id"] for s in by_email.json()["items"]} == {"student-2"}
    by_roll = ctx.client.get("/api/v1/students?q=R-student-1", headers=admin)
    assert {s["id"] for s in by_roll.json()["items"]} == {"student-1"}

    trainer_view = ctx.client.get("/api/v1/students", headers=trainer)
    assert trainer_view.status_code == 200
    assert len(trainer_view.json()["items"]) == 2

    self_view = ctx.client.get("/api/v1/students", headers=student)
    assert self_view.status_code == 200
    assert [s["id"] for s in self_view.json()["items"]] == ["student-1"]


def test_other_college_student_is_hidden(ctx):
    setup_college(ctx, "college-1", "One")
    setup_college(ctx, "college-2", "Two")
    setup_batch(ctx, batch_id="batch-2", college_id="college-2", trainer_id="trainer-2")
    setup_student(ctx, "student-x", uid="uid-student-x", college_id="college-2", batch_id="batch-2")
    setup_batch(ctx)
    setup_student(ctx)

    ctx.seed_user("admin-1", "admin", college_ids=["college-1"])
    response = ctx.client.get("/api/v1/students", headers=ctx.headers("admin-1"))
    assert response.status_code == 200
    assert [s["id"] for s in response.json()["items"]] == ["student-1"]

    direct = ctx.client.get("/api/v1/students/student-x", headers=ctx.headers("admin-1"))
    assert direct.status_code == 403


def test_profile_edit_permissions_and_score(ctx):
    _setup(ctx)
    student = ctx.headers("uid-student-1")
    trainer = ctx.headers("trainer-1")
    admin = ctx.headers("admin-1")

    personal = ctx.client.patch(
        "/api/v1/students/student-1",
        headers=student,
        json={"phone": "+91 99999 11111", "skills": ["python"]},
    )
    assert personal.status_code == 200, personal.text
    assert personal.json()["phone"] == "+91 99999 11111"
    assert personal.json()["profileScore"] < 100

    academic = ctx.client.patch(
        "/api/v1/students/student-1", headers=student, json={"cgpa": 9.1}
    )
    assert academic.status_code == 403
    assert academic.json()["code"] == "field_forbidden"

    trainer_academic = ctx.client.patch(
        "/api/v1/students/student-1", headers=trainer, json={"cgpa": 9.1}
    )
    assert trainer_academic.status_code == 200
    assert trainer_academic.json()["cgpa"] == 9.1

    trainer_personal = ctx.client.patch(
        "/api/v1/students/student-1", headers=trainer, json={"phone": "123"}
    )
    assert trainer_personal.status_code == 403

    admin_placement = ctx.client.patch(
        "/api/v1/students/student-1",
        headers=admin,
        json={"placementStatus": "in_process"},
    )
    assert admin_placement.status_code == 200
    assert admin_placement.json()["placementStatus"] == "in_process"


def test_student_cannot_read_another_profile(ctx):
    _setup(ctx)
    response = ctx.client.get("/api/v1/students/student-2", headers=ctx.headers("uid-student-1"))
    assert response.status_code == 403
    assert response.json()["code"] == "student_forbidden"


def test_csv_import_reports_bad_rows(ctx):
    setup_college(ctx)
    admin = ctx.headers("admin-1")
    csv_data = (
        "name,email,collegeId,branch,cgpa,skills\n"
        "Good Student,good@spms.test,college-1,CSE,8.2,python;sql\n"
        "Bad College,bad@spms.test,college-404,CSE,7.0,python\n"
        "Bad Email,not-an-email,college-1,CSE,7.0,\n"
    )
    response = ctx.client.post(
        "/api/v1/students/import",
        headers=admin,
        files={"file": ("students.csv", csv_data, "text/csv")},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["created"] == 1
    assert body["failed"] == 2
    assert {error["row"] for error in body["errors"]} == {3, 4}
    assert ctx.store.query("students", [("email", "==", "good@spms.test")])


def test_resume_upload_and_signed_url(ctx):
    _setup(ctx)
    student = ctx.headers("uid-student-1")
    response = ctx.client.post(
        "/api/v1/students/student-1/resume",
        headers=student,
        files={"file": ("cv.pdf", b"%PDF-1.4 fake", "application/pdf")},
    )
    assert response.status_code == 200, response.text
    assert response.json()["resumeUrl"].startswith("local://storage/")

    bad = ctx.client.post(
        "/api/v1/students/student-1/resume",
        headers=student,
        files={"file": ("cv.txt", b"nope", "text/plain")},
    )
    assert bad.status_code == 400

    url = ctx.client.get("/api/v1/students/student-1/resume-url", headers=student)
    assert url.status_code == 200
    assert url.json()["resumePath"].endswith(".pdf")


def test_pagination_cursor(ctx):
    setup_college(ctx)
    for index in range(5):
        setup_student(ctx, f"student-{index}", uid=f"uid-student-{index}")

    first = ctx.client.get("/api/v1/students?limit=2", headers=ctx.headers("admin-1"))
    body = first.json()
    assert len(body["items"]) == 2
    assert body["nextCursor"]

    second = ctx.client.get(
        f"/api/v1/students?limit=2&cursor={body['nextCursor']}",
        headers=ctx.headers("admin-1"),
    )
    assert second.status_code == 200
    assert len(second.json()["items"]) == 2
    assert {s["id"] for s in body["items"]}.isdisjoint({s["id"] for s in second.json()["items"]})
