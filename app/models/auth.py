"""Auth schemas."""

from __future__ import annotations

from app.models.common import CamelModel
from app.models.enums import Role
from app.models.student import Student
from app.models.user import User


class MeResponse(CamelModel):
    uid: str
    role: Role
    college_ids: list[str]
    super_admin: bool
    name: str
    email: str
    user: User | None = None
    student: Student | None = None


class LogoutAllResponse(CamelModel):
    message: str
    revoked: bool = True
