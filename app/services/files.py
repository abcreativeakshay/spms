"""File uploads with validation + short-lived signed URLs (NFR privacy)."""

from __future__ import annotations

import os
import re
import uuid

from fastapi import UploadFile

from app.core.config import settings
from app.core.errors import BadRequest
from app.core.firebase import StorageGateway, get_storage

_SAFE = re.compile(r"[^A-Za-z0-9._-]+")

ALLOWED_DOCUMENT_TYPES = {
    "application/pdf": ".pdf",
    "image/png": ".png",
    "image/jpeg": ".jpg",
}
RESUME_TYPES = {"application/pdf": ".pdf"}
MAX_RESUME_BYTES = 5 * 1024 * 1024
MAX_OFFER_BYTES = 10 * 1024 * 1024


class FileService:
    def __init__(self, storage: StorageGateway | None = None) -> None:
        self.storage = storage or get_storage()

    async def _read(self, upload: UploadFile, *, max_bytes: int) -> bytes:
        data = await upload.read()
        if not data:
            raise BadRequest("Uploaded file is empty")
        if len(data) > max_bytes:
            raise BadRequest(f"File exceeds {max_bytes // (1024 * 1024)} MB limit")
        return data

    @staticmethod
    def _ext(upload: UploadFile, allowed: dict[str, str], label: str) -> str:
        content_type = (upload.content_type or "").split(";")[0].strip()
        if content_type not in allowed:
            raise BadRequest(f"{label} must be one of: {', '.join(sorted(allowed))}")
        return allowed[content_type]

    async def upload_resume(self, *, college_id: str, student_id: str, upload: UploadFile) -> str:
        ext = self._ext(upload, RESUME_TYPES, "Resume")
        data = await self._read(upload, max_bytes=MAX_RESUME_BYTES)
        safe_name = _SAFE.sub("_", os.path.basename(upload.filename or "resume"))
        path = f"resumes/{college_id}/{student_id}/{uuid.uuid4().hex}_{safe_name}{ext}"
        return self.storage.upload(path, data, "application/pdf")

    async def upload_offer_letter(self, *, college_id: str, application_id: str, upload: UploadFile) -> str:
        ext = self._ext(upload, ALLOWED_DOCUMENT_TYPES, "Offer letter")
        data = await self._read(upload, max_bytes=MAX_OFFER_BYTES)
        safe_name = _SAFE.sub("_", os.path.basename(upload.filename or "offer"))
        path = f"offers/{college_id}/{application_id}/{uuid.uuid4().hex}_{safe_name}{ext}"
        return self.storage.upload(path, data, upload.content_type or "application/octet-stream")

    def signed_url(self, path: str | None) -> str | None:
        if not path:
            return None
        return self.storage.signed_url(path, settings.signed_url_ttl_seconds)
