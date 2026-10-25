"""User account schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field, field_validator

from app.models.common import CamelModel
from app.models.enums import Role


def _validate_email(value: str) -> str:
    if "@" not in value or value.startswith("@") or value.endswith("@"):
        raise ValueError("Invalid email address")
    return value.lower()


class UserBase(CamelModel):
    name: str = Field(min_length=2, max_length=120)
    email: str
    role: Role
    college_ids: list[str] = Field(default_factory=list)
    phone: str | None = None
    super_admin: bool = False
    active: bool = True

    _email = field_validator("email")(_validate_email)


class UserCreate(UserBase):
    password: str | None = Field(default=None, min_length=8)
    # Optional student onboarding payload (flat, so the admin UI is one form).
    college_id: str | None = None
    batch_id: str | None = None
    roll_no: str | None = None
    degree: str | None = None
    branch: str | None = None
    grad_year: int | None = Field(default=None, ge=1990, le=2100)
    cgpa: float | None = Field(default=None, ge=0, le=10)
    skills: list[str] = Field(default_factory=list)
    send_setup_email: bool = True


class UserUpdate(CamelModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    phone: str | None = None
    role: Role | None = None
    college_ids: list[str] | None = None
    super_admin: bool | None = None
    active: bool | None = None


class User(CamelModel):
    id: str
    uid: str
    name: str
    email: str
    role: Role
    college_ids: list[str] = Field(default_factory=list)
    phone: str | None = None
    super_admin: bool = False
    active: bool = True
    created_at: datetime | None = None
    updated_at: datetime | None = None
    last_login_at: datetime | None = None


class UserListResponse(CamelModel):
    items: list[User]
    next_cursor: str | None = None


class UserCreated(CamelModel):
    user: User
    setup_link: str | None = None


class BulkRowError(CamelModel):
    row: int
    email: str | None = None
    message: str


class BulkImportResult(CamelModel):
    created: int = 0
    failed: int = 0
    errors: list[BulkRowError] = Field(default_factory=list)
    setup_links: dict[str, str] = Field(default_factory=dict)
