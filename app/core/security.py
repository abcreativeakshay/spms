"""Authentication + RBAC dependencies. Every router uses these."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings
from app.core.errors import Forbidden, Unauthorized
from app.core.firebase import TokenVerifier, get_token_verifier
from app.models.enums import Role
from app.repositories.store import DocumentStore, get_store

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass
class Principal:
    uid: str
    role: Role
    college_ids: list[str] = field(default_factory=list)
    super_admin: bool = False
    name: str = ""
    email: str = ""
    active: bool = True

    @property
    def is_admin(self) -> bool:
        return self.role == Role.ADMIN

    @property
    def is_trainer(self) -> bool:
        return self.role == Role.TRAINER

    @property
    def is_student(self) -> bool:
        return self.role == Role.STUDENT


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    verifier: TokenVerifier = Depends(get_token_verifier),
    store: DocumentStore = Depends(get_store),
) -> Principal:
    if credentials is None or not credentials.credentials:
        raise Unauthorized("Missing bearer token")

    try:
        claims = verifier.verify(credentials.credentials)
    except Unauthorized:
        raise
    except Exception as exc:  # noqa: BLE001 - SDK raises many exception types
        raise Unauthorized("Token verification failed") from exc

    uid = claims.get("uid") or claims.get("sub")
    if not uid:
        raise Unauthorized("Token has no subject")

    user_doc = store.get("users", uid)
    if user_doc is None:
        raise Forbidden(
            "User profile is not provisioned. Ask an administrator to create your account.",
            code="user_not_provisioned",
        )
    if user_doc.get("active", True) is False:
        raise Forbidden("Account is disabled", code="account_disabled")

    raw_role = claims.get("role") or user_doc.get("role")
    try:
        role = Role(raw_role)
    except ValueError as exc:
        raise Forbidden("Token carries an invalid role", code="invalid_role") from exc

    college_ids = claims.get("collegeIds")
    if college_ids is None:
        college_ids = user_doc.get("collegeIds", [])

    principal = Principal(
        uid=uid,
        role=role,
        college_ids=list(college_ids or []),
        super_admin=bool(claims.get("superAdmin") or user_doc.get("superAdmin")),
        name=user_doc.get("name", claims.get("name", "")),
        email=user_doc.get("email", claims.get("email", "")),
        active=True,
    )
    return principal


def require_roles(*roles: Role | str) -> Callable[..., Principal]:
    allowed = {Role(r) for r in roles}

    async def _dep(user: Principal = Depends(get_current_user)) -> Principal:
        if user.role not in allowed:
            raise Forbidden(
                f"Requires one of roles: {', '.join(sorted(r.value for r in allowed))}",
                code="role_forbidden",
            )
        return user

    return _dep


def require_admin(user: Principal = Depends(require_roles(Role.ADMIN))) -> Principal:
    return user


def require_staff(user: Principal = Depends(require_roles(Role.ADMIN, Role.TRAINER))) -> Principal:
    return user


def readiness_weights() -> dict[str, float]:
    return settings.readiness_weights
