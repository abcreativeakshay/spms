"""Service-account bootstrap: inline JSON (plain or base64) must work without a key file."""

from __future__ import annotations

import base64
import json

import pytest

from app.core import firebase as fb

ACCOUNT = {
    "type": "service_account",
    "project_id": "placement-app-144e3",
    "private_key": "-----BEGIN PRIVATE KEY-----\\nabc\\n-----END PRIVATE KEY-----\\n",
    "client_email": "api@placement-app-144e3.iam.gserviceaccount.com",
}


def test_inline_json_is_accepted_verbatim():
    assert fb._decode_service_account(json.dumps(ACCOUNT))["project_id"] == "placement-app-144e3"


def test_base64_json_is_decoded():
    encoded = base64.b64encode(json.dumps(ACCOUNT).encode()).decode()
    assert fb._decode_service_account(encoded)["project_id"] == "placement-app-144e3"


def test_escaped_newlines_in_private_key_are_restored():
    decoded = fb._decode_service_account(json.dumps(ACCOUNT))
    assert decoded["private_key"].count("\n") == 3


def test_garbage_is_rejected_with_a_clear_error():
    with pytest.raises(ValueError, match="base64-encoded JSON"):
        fb._decode_service_account("not-a-service-account")


def test_truncated_env_value_points_at_secret_files():
    long_key = "-----BEGIN PRIVATE KEY-----\\n" + "A" * 1700 + "\\n-----END PRIVATE KEY-----\\n"
    truncated = json.dumps({**ACCOUNT, "private_key": long_key})[:1888]
    with pytest.raises(ValueError, match="secret file"):
        fb._parse_inline_credentials(truncated)


def test_credential_source_names_a_missing_file(monkeypatch, tmp_path):
    monkeypatch.setattr(fb.settings, "google_application_credentials", str(tmp_path / "nope.json"))
    monkeypatch.setattr(fb.settings, "google_application_credentials_json", None)
    assert fb.credential_source() == {
        "source": "missing_file",
        "path": str(tmp_path / "nope.json"),
        "inlineChars": 0,
    }


def test_credential_source_prefers_an_existing_file(monkeypatch, tmp_path):
    key = tmp_path / "sa.json"
    key.write_text(json.dumps(ACCOUNT))
    monkeypatch.setattr(fb.settings, "google_application_credentials", str(key))
    monkeypatch.setattr(fb.settings, "google_application_credentials_json", json.dumps(ACCOUNT))
    info = fb.credential_source()
    assert info["source"] == "file"
    assert info["bytes"] == key.stat().st_size
