"""Firebase Admin SDK bootstrap + provider abstractions.

Two providers exist so the app (and the test suite) can run without project
credentials:

* Firebase*  — real Admin SDK (also used against the emulator suite)
* Local*     — in-process stand-ins used when ``USE_FIREBASE=false``
"""

from __future__ import annotations

import os
import uuid
from functools import lru_cache
from typing import Any, Protocol
from urllib.parse import quote

from app.core.config import settings


# --------------------------------------------------------------------------- #
# Bootstrap
# --------------------------------------------------------------------------- #
def _apply_emulator_env() -> None:
    mapping = {
        "FIREBASE_AUTH_EMULATOR_HOST": settings.firebase_auth_emulator_host,
        "FIRESTORE_EMULATOR_HOST": settings.firestore_emulator_host,
        "FIREBASE_STORAGE_EMULATOR_HOST": settings.firebase_storage_emulator_host,
    }
    for key, value in mapping.items():
        if value and not os.environ.get(key):
            os.environ[key] = value


def init_firebase() -> Any:
    """Initialise (once) and return the firebase_admin app."""
    import firebase_admin
    from firebase_admin import credentials

    _apply_emulator_env()
    if firebase_admin._apps:  # noqa: SLF001 - documented singleton
        return firebase_admin.get_app()

    cred: Any
    cred_path = settings.google_application_credentials
    if cred_path and os.path.exists(cred_path):
        cred = credentials.Certificate(cred_path)
    else:
        cred = credentials.ApplicationDefault()

    options = {
        "projectId": settings.firebase_project_id,
        "storageBucket": settings.firebase_storage_bucket,
    }
    return firebase_admin.initialize_app(cred, options)


def get_firestore_client() -> Any:
    from firebase_admin import firestore

    init_firebase()
    return firestore.client()


def is_emulator() -> bool:
    return bool(settings.firestore_emulator_host or os.environ.get("FIRESTORE_EMULATOR_HOST"))


# --------------------------------------------------------------------------- #
# Token verification
# --------------------------------------------------------------------------- #
class TokenVerifier(Protocol):
    def verify(self, token: str) -> dict[str, Any]: ...


class FirebaseTokenVerifier:
    def verify(self, token: str) -> dict[str, Any]:
        from firebase_admin import auth

        init_firebase()
        return auth.verify_id_token(token, check_revoked=True)


class LocalTokenVerifier:
    """Development verifier: ``dev:<uid>[:<role>]`` bearer tokens.

    Only enabled when ``ALLOW_DEV_TOKENS=true``; claims for role/collegeIds are
    read from the users document by ``get_current_user`` when absent here.
    """

    def verify(self, token: str) -> dict[str, Any]:
        from app.core.errors import Unauthorized

        if not (settings.allow_dev_tokens or not settings.use_firebase):
            raise Unauthorized("Development tokens are disabled")
        if not token.startswith("dev:"):
            raise Unauthorized("Malformed development token")
        parts = token.split(":")
        if len(parts) < 2 or not parts[1]:
            raise Unauthorized("Malformed development token")
        claims: dict[str, Any] = {"uid": parts[1]}
        if len(parts) > 2:
            claims["role"] = parts[2]
        return claims


@lru_cache
def get_token_verifier() -> TokenVerifier:
    return FirebaseTokenVerifier() if settings.use_firebase else LocalTokenVerifier()


# --------------------------------------------------------------------------- #
# Auth user administration
# --------------------------------------------------------------------------- #
class AuthProvider(Protocol):
    def create_user(
        self, *, email: str, password: str | None, display_name: str, claims: dict[str, Any]
    ) -> str: ...

    def set_claims(self, uid: str, claims: dict[str, Any]) -> None: ...

    def revoke_tokens(self, uid: str) -> None: ...

    def password_reset_link(self, email: str) -> str | None: ...

    def update_user(self, uid: str, **fields: Any) -> None: ...

    def delete_user(self, uid: str) -> None: ...


class FirebaseAuthProvider:
    def create_user(
        self, *, email: str, password: str | None, display_name: str, claims: dict[str, Any]
    ) -> str:
        from firebase_admin import auth

        init_firebase()
        user = auth.create_user(
            email=email,
            password=password,
            display_name=display_name,
            email_verified=False,
            disabled=False,
        )
        auth.set_custom_user_claims(user.uid, claims)
        return user.uid

    def set_claims(self, uid: str, claims: dict[str, Any]) -> None:
        from firebase_admin import auth

        auth.set_custom_user_claims(uid, claims)

    def revoke_tokens(self, uid: str) -> None:
        from firebase_admin import auth

        auth.revoke_refresh_tokens(uid)

    def password_reset_link(self, email: str) -> str | None:
        from firebase_admin import auth

        try:
            return auth.generate_password_reset_link(email)
        except Exception:  # noqa: BLE001 - best effort onboarding email
            return None

    def update_user(self, uid: str, **fields: Any) -> None:
        from firebase_admin import auth

        auth.update_user(uid, **fields)

    def delete_user(self, uid: str) -> None:
        from firebase_admin import auth

        auth.delete_user(uid)


class LocalAuthProvider:
    """No-op provider for local dev/tests; the users document is the source of truth."""

    def create_user(
        self, *, email: str, password: str | None, display_name: str, claims: dict[str, Any]
    ) -> str:
        return f"local_{uuid.uuid4().hex[:20]}"

    def set_claims(self, uid: str, claims: dict[str, Any]) -> None:
        return None

    def revoke_tokens(self, uid: str) -> None:
        return None

    def password_reset_link(self, email: str) -> str | None:
        return f"http://localhost:5173/setup-password?email={quote(email)}"

    def update_user(self, uid: str, **fields: Any) -> None:
        return None

    def delete_user(self, uid: str) -> None:
        return None


@lru_cache
def get_auth_provider() -> AuthProvider:
    return FirebaseAuthProvider() if settings.use_firebase else LocalAuthProvider()


# --------------------------------------------------------------------------- #
# Cloud Storage
# --------------------------------------------------------------------------- #
class StorageGateway(Protocol):
    def upload(self, path: str, data: bytes, content_type: str) -> str: ...

    def signed_url(self, path: str, ttl_seconds: int) -> str: ...

    def delete(self, path: str) -> None: ...


class LocalStorage:
    """Stores blobs in memory; URLs are fake but stable for tests/dev."""

    def __init__(self) -> None:
        self._blobs: dict[str, tuple[bytes, str]] = {}

    def upload(self, path: str, data: bytes, content_type: str) -> str:
        self._blobs[path] = (data, content_type)
        return path

    def signed_url(self, path: str, ttl_seconds: int) -> str:
        return f"local://storage/{path}?ttl={ttl_seconds}"

    def delete(self, path: str) -> None:
        self._blobs.pop(path, None)

    def read(self, path: str) -> tuple[bytes, str] | None:
        return self._blobs.get(path)


class FirebaseStorage:
    def _bucket(self) -> Any:
        from firebase_admin import storage

        init_firebase()
        return storage.bucket()

    @staticmethod
    def _unavailable(exc: Exception) -> Any:
        from app.core.errors import ServiceUnavailable

        return ServiceUnavailable(
            "Cloud Storage is unavailable for this project. Uploads and signed URLs "
            "need an existing Storage bucket.",
            code="storage_unavailable",
            details={"bucket": settings.firebase_storage_bucket},
        )

    def _guarded(self, call: Any) -> Any:
        from app.core.errors import ServiceUnavailable
        from google.api_core.exceptions import GoogleAPIError

        try:
            return call()
        except (GoogleAPIError, ValueError, OSError) as exc:
            raise self._unavailable(exc) from exc
        except ServiceUnavailable:
            raise

    def upload(self, path: str, data: bytes, content_type: str) -> str:
        def _upload() -> str:
            blob = self._bucket().blob(path)
            blob.upload_from_string(data, content_type=content_type)
            return path

        return self._guarded(_upload)

    def signed_url(self, path: str, ttl_seconds: int) -> str:
        from datetime import timedelta

        if is_emulator() or settings.firebase_storage_emulator_host:
            host = settings.firebase_storage_emulator_host or os.environ.get(
                "FIREBASE_STORAGE_EMULATOR_HOST", "127.0.0.1:9199"
            )
            bucket = settings.firebase_storage_bucket
            return f"http://{host}/v0/b/{bucket}/o/{quote(path, safe='')}?alt=media"

        def _sign() -> str:
            blob = self._bucket().blob(path)
            return blob.generate_signed_url(
                version="v4", expiration=timedelta(seconds=ttl_seconds)
            )

        return self._guarded(_sign)

    def delete(self, path: str) -> None:
        def _delete() -> None:
            self._bucket().blob(path).delete()

        self._guarded(_delete)


_storage_singleton: StorageGateway | None = None


def get_storage() -> StorageGateway:
    global _storage_singleton
    if _storage_singleton is None:
        _storage_singleton = FirebaseStorage() if settings.use_firebase else LocalStorage()
    return _storage_singleton
