"""Storage failures surface as a clean 503 instead of a 500."""

from __future__ import annotations

import pytest
from google.api_core.exceptions import NotFound

from app.core.errors import ServiceUnavailable
from app.core.firebase import FirebaseStorage


@pytest.fixture
def missing_bucket(monkeypatch):
    storage = FirebaseStorage()

    def boom():
        raise NotFound("The specified bucket does not exist.")

    monkeypatch.setattr(storage, "_bucket", boom)
    return storage


def test_upload_without_bucket_is_service_unavailable(missing_bucket):
    with pytest.raises(ServiceUnavailable) as exc:
        missing_bucket.upload("resumes/x/cv.pdf", b"%PDF-1.4", "application/pdf")
    assert exc.value.status_code == 503
    assert exc.value.code == "storage_unavailable"
    assert exc.value.details["bucket"]


def test_signed_url_and_delete_without_bucket_are_guarded(missing_bucket):
    with pytest.raises(ServiceUnavailable):
        missing_bucket.signed_url("resumes/x/cv.pdf", 300)
    with pytest.raises(ServiceUnavailable):
        missing_bucket.delete("resumes/x/cv.pdf")
