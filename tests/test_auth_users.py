"""Phase 0/1: authentication, RBAC and onboarding."""

from __future__ import annotations


def test_health_is_public(ctx):
    response = ctx.client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_missing_token_is_401(ctx):
    response = ctx.client.get("/api/v1/auth/me")
    assert response.status_code == 401
    assert response.json()["code"] == "unauthorized"


def test_unprovisioned_user_is_403(ctx):
    response = ctx.client.get("/api/v1/auth/me", headers=ctx.headers("ghost"))
    assert response.status_code == 403
    assert response.json()["code"] == "user_not_provisioned"


def test_me_returns_role_and_college_scope(ctx):
    ctx.seed_college()
    ctx.seed_user("admin-1", "admin", college_ids=["college-1"])
    response = ctx.client.get("/api/v1/auth/me", headers=ctx.headers("admin-1"))
    assert response.status_code == 200
    body = response.json()
    assert body["role"] == "admin"
    assert body["collegeIds"] == ["college-1"]


def test_student_cannot_create_college(ctx):
    ctx.seed_college()
    ctx.seed_user("student-user", "student", college_ids=["college-1"])
    response = ctx.client.post(
        "/api/v1/colleges",
        headers=ctx.headers("student-user"),
        json={"name": "Nope"},
    )
    assert response.status_code == 403
    assert response.json()["code"] == "role_forbidden"


def test_admin_creates_trainer_and_student(ctx):
    ctx.seed_college()
    ctx.seed_user("admin-1", "admin", college_ids=["college-1"])

    trainer = ctx.client.post(
        "/api/v1/users",
        headers=ctx.headers("admin-1"),
        json={
            "name": "Trainer One",
            "email": "trainer@spms.test",
            "role": "trainer",
            "collegeIds": ["college-1"],
        },
    )
    assert trainer.status_code == 201, trainer.text
    trainer_uid = trainer.json()["user"]["uid"]
    assert trainer.json()["setupLink"]

    student = ctx.client.post(
        "/api/v1/users",
        headers=ctx.headers("admin-1"),
        json={
            "name": "Student One",
            "email": "student@spms.test",
            "role": "student",
            "collegeId": "college-1",
            "rollNo": "R1",
            "cgpa": 8.4,
            "branch": "CSE",
        },
    )
    assert student.status_code == 201, student.text
    student_uid = student.json()["user"]["uid"]

    # Student can read their own profile but not the trainer's.
    me = ctx.client.get("/api/v1/auth/me", headers=ctx.headers(student_uid))
    assert me.status_code == 200
    assert me.json()["student"]["rollNo"] == "R1"

    profile = ctx.client.get("/api/v1/students/me", headers=ctx.headers(student_uid))
    assert profile.status_code == 200
    assert profile.json()["collegeId"] == "college-1"

    forbidden = ctx.client.get("/api/v1/users", headers=ctx.headers(student_uid))
    assert forbidden.status_code == 403

    # Trainer cannot create users either.
    trainer_me = ctx.client.get("/api/v1/auth/me", headers=ctx.headers(trainer_uid))
    assert trainer_me.json()["role"] == "trainer"


def test_college_scope_isolation(ctx):
    ctx.seed_college("college-1", "One")
    ctx.seed_college("college-2", "Two")
    ctx.seed_user("admin-1", "admin", college_ids=["college-1"])
    ctx.seed_user("admin-2", "admin", college_ids=["college-2"], super_admin=True)

    one = ctx.client.get("/api/v1/colleges/college-1", headers=ctx.headers("admin-1"))
    two = ctx.client.get("/api/v1/colleges/college-2", headers=ctx.headers("admin-1"))
    assert one.status_code == 200
    assert two.status_code == 403
    assert two.json()["code"] == "college_scope_violation"

    all_colleges = ctx.client.get("/api/v1/colleges", headers=ctx.headers("admin-2"))
    assert all_colleges.status_code == 200
    names = {item["name"] for item in all_colleges.json()["items"]}
    assert names == {"One", "Two"}


def test_disable_revokes_access(ctx):
    ctx.seed_college()
    ctx.seed_user("admin-1", "admin", college_ids=["college-1"])
    created = ctx.client.post(
        "/api/v1/users",
        headers=ctx.headers("admin-1"),
        json={
            "name": "Temp Trainer",
            "email": "temp@spms.test",
            "role": "trainer",
            "collegeIds": ["college-1"],
        },
    ).json()
    uid = created["user"]["uid"]
    assert ctx.client.get("/api/v1/auth/me", headers=ctx.headers(uid)).status_code == 200

    disabled = ctx.client.post(f"/api/v1/users/{uid}/disable", headers=ctx.headers("admin-1"))
    assert disabled.status_code == 200
    assert disabled.json()["active"] is False

    after = ctx.client.get("/api/v1/auth/me", headers=ctx.headers(uid))
    assert after.status_code == 403
    assert after.json()["code"] == "account_disabled"
