#!/usr/bin/env python
"""Create (or promote) an SPMS super administrator.

Creates the Firebase Authentication account, sets the ``role``/``superAdmin``
custom claims, and writes the matching ``users`` document.

    .venv/bin/python scripts/create_super_admin.py \
        --email admin@spms.test --name "Placement Admin"

Against the emulator:

    FIREBASE_AUTH_EMULATOR_HOST=127.0.0.1:9099 \
    FIRESTORE_EMULATOR_HOST=127.0.0.1:8081 \
    USE_FIREBASE=true .venv/bin/python scripts/create_super_admin.py \
        --email admin@spms.test --password 'ChangeMe123!'

If ``--password`` is omitted (and ``SUPER_ADMIN_PASSWORD`` is unset) a random
password is generated and printed once. No credentials are stored in the repo.
"""

from __future__ import annotations

import argparse
import os
import secrets
import sys

from app.core.firebase import get_auth_provider
from app.repositories import Repos
from app.repositories.store import MemoryStore, get_store
from app.services.audit import AuditService
from app.services.metrics import utcnow


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create an SPMS super administrator")
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", default="Super Admin")
    parser.add_argument("--password", default=os.getenv("SUPER_ADMIN_PASSWORD"))
    parser.add_argument(
        "--college-id",
        action="append",
        default=[],
        help="Optional college scope. Omit for a global super admin (all colleges).",
    )
    args = parser.parse_args(argv)

    email = args.email.strip().lower()
    if "@" not in email:
        print(f"Invalid email: {email}", file=sys.stderr)
        return 2

    generated = False
    password = args.password
    if not password:
        password = secrets.token_urlsafe(12)
        generated = True
    elif len(password) < 8:
        print("Password must be at least 8 characters", file=sys.stderr)
        return 2

    store = get_store()
    repos = Repos(store)
    auth = get_auth_provider()

    if isinstance(store, MemoryStore):
        print(
            "WARNING: USE_FIREBASE=false uses an in-memory store. The account will vanish\n"
            "         when this process exits. Set USE_FIREBASE=true for a real account.",
            file=sys.stderr,
        )

    claims = {
        "role": "admin",
        "collegeIds": args.college_id or ["*"],
        "superAdmin": True,
    }

    existing = repos.users.by_email(email)
    if existing:
        uid = existing["uid"]
        auth.set_claims(uid, claims)
        auth.update_user(uid, password=password, display_name=args.name, disabled=False)
        repos.users.update(
            uid,
            {
                "name": args.name,
                "role": "admin",
                "collegeIds": args.college_id or ["*"],
                "superAdmin": True,
                "active": True,
                "updatedAt": utcnow(),
            },
        )
        action = "promoted"
    else:
        uid = auth.create_user(
            email=email,
            password=password,
            display_name=args.name,
            claims=claims,
        )
        now = utcnow()
        repos.users.set(
            {
                "uid": uid,
                "name": args.name,
                "email": email,
                "role": "admin",
                "collegeIds": args.college_id or ["*"],
                "superAdmin": True,
                "active": True,
                "createdAt": now,
                "updatedAt": now,
            },
            doc_id=uid,
        )
        action = "created"

    AuditService(repos).record(
        None,
        f"user.{action}",
        "user",
        uid,
        after={"email": email, "role": "admin", "superAdmin": True},
    )

    print(f"Super admin {action}: {email}")
    print(f"  uid: {uid}")
    if generated:
        print(f"  password: {password}")
        print("  (generated once; change it after first login)")
    else:
        print("  password: set from --password/SUPER_ADMIN_PASSWORD")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
