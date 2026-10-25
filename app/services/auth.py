"""Session helpers for the authenticated principal."""

from __future__ import annotations

from typing import Any

from app.core.firebase import AuthProvider, get_auth_provider
from app.core.security import Principal
from app.repositories import Repos


class AuthService:
    def __init__(self, repos: Repos, auth: AuthProvider | None = None) -> None:
        self.repos = repos
        self.auth = auth or get_auth_provider()

    def me(self, actor: Principal) -> dict[str, Any]:
        user = self.repos.users.get(actor.uid) or {
            "id": actor.uid,
            "uid": actor.uid,
            "name": actor.name,
            "email": actor.email,
            "role": actor.role.value,
            "collegeIds": actor.college_ids,
            "superAdmin": actor.super_admin,
            "active": True,
        }
        student = self.repos.students.by_uid(actor.uid)
        return {
            "uid": actor.uid,
            "role": actor.role.value,
            "collegeIds": actor.college_ids,
            "superAdmin": actor.super_admin,
            "name": actor.name,
            "email": actor.email,
            "user": user,
            "student": student,
        }

    def logout_all(self, actor: Principal) -> dict[str, Any]:
        self.auth.revoke_tokens(actor.uid)
        return {"message": "All refresh tokens revoked. Sign in again.", "revoked": True}
