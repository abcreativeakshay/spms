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
