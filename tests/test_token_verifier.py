"""Token verification should stay local unless revocation checks are requested."""

from __future__ import annotations

import firebase_admin.auth

from app.core import firebase as fb


def test_firebase_verifier_skips_revocation_lookup_by_default(monkeypatch):
    seen: dict[str, object] = {}

    def fake_verify(token: str, **kwargs: object) -> dict[str, str]:
        seen["token"] = token
        seen.update(kwargs)
        return {"uid": "user-1"}

    monkeypatch.setattr(fb, "init_firebase", lambda: None)
    monkeypatch.setattr(firebase_admin.auth, "verify_id_token", fake_verify)

    assert fb.FirebaseTokenVerifier().verify("id-token") == {"uid": "user-1"}
    assert seen["token"] == "id-token"
    assert seen["check_revoked"] is False
