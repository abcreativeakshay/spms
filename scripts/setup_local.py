"""Prepare a local, Firebase-backed checkout.

Creates ``.env`` and ``web/.env`` from the checked-in examples, points the API at a
service-account key under ``secrets/``, and can verify the connection.

    # 1. put the key in place (the project owner sends it to you)
    python3 scripts/setup_local.py --service-account ~/Downloads/placement-app.json

    # 2. verify Firestore + Auth before starting the servers
    .venv/bin/python scripts/setup_local.py --check

    # 3. run
    .venv/bin/uvicorn app.main:app --port 8080
    cd web && npm install && npm run dev

The key is never written to git: ``secrets/`` is ignored.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KEY_PATH = ROOT / "secrets" / "service-account.json"

REQUIRED_KEYS = ("type", "project_id", "private_key", "client_email")


def upsert(path: Path, *, required: dict[str, str], defaults: dict[str, str]) -> None:
    """Update KEY=value lines, keeping comments and order; append anything missing."""
    lines = path.read_text().splitlines() if path.exists() else []
    seen: set[str] = set()
    out: list[str] = []
    for line in lines:
        text = line.strip()
        if text and not text.startswith("#") and "=" in text:
            key, _, value = line.partition("=")
            key = key.strip()
            if key in required:
                seen.add(key)
                out.append(f"{key}={required[key]}")
                continue
            if key in defaults:
                seen.add(key)
                out.append(line if value.strip() else f"{key}={defaults[key]}")
                continue
        out.append(line)
    for key, value in {**defaults, **required}.items():
        if key not in seen:
            out.append(f"{key}={value}")
    path.write_text("\n".join(out).rstrip() + "\n")


def load_key(path: Path) -> dict[str, str]:
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"{path} is not readable JSON: {exc}") from exc
    missing = [key for key in REQUIRED_KEYS if not data.get(key)]
    if data.get("type") != "service_account" or missing:
        raise SystemExit(
            f"{path} is not a service-account key (missing: {missing or 'none'}; "
            f"type={data.get('type')!r}). Download it from Firebase console -> "
            "Project settings -> Service accounts -> Generate new private key."
        )
    return data


def install_key(source: str | None) -> dict[str, str]:
    if source:
        origin = Path(source).expanduser()
        KEY_PATH.parent.mkdir(exist_ok=True)
        if origin.resolve() != KEY_PATH.resolve():
            shutil.copy2(origin, KEY_PATH)
        KEY_PATH.chmod(0o600)
        print(f"service account -> {KEY_PATH.relative_to(ROOT)}")
    elif not KEY_PATH.exists():
        inline = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS_JSON")
        if not inline:
            raise SystemExit(
                "No service-account key found.\n"
                "Pass one with --service-account /path/to/key.json, or place it at "
                f"{KEY_PATH.relative_to(ROOT)}.\n"
                "The project owner can download it from Firebase console -> Project "
                "settings -> Service accounts -> Generate new private key."
            )
        KEY_PATH.parent.mkdir(exist_ok=True)
        KEY_PATH.write_text(inline)
        KEY_PATH.chmod(0o600)
        print(f"service account <- GOOGLE_APPLICATION_CREDENTIALS_JSON -> {KEY_PATH.name}")
    return load_key(KEY_PATH)


def configure(key: dict[str, str]) -> None:
    project = key["project_id"]
    env_path = ROOT / ".env"
    example = ROOT / ".env.example"
    if not env_path.exists():
        shutil.copy2(example, env_path)
        print(".env <- .env.example")
    upsert(
        env_path,
        required={
            "USE_FIREBASE": "true",
            "FIREBASE_PROJECT_ID": project,
            "GOOGLE_APPLICATION_CREDENTIALS": "./secrets/service-account.json",
            "SEED_DEMO": "false",
            "ALLOW_DEV_TOKENS": "false",
        },
        defaults={
            "FIREBASE_STORAGE_BUCKET": f"{project}.firebasestorage.app",
            "CORS_ORIGINS": "http://127.0.0.1:5173,http://localhost:5173",
            "FIRESTORE_WARM_CACHE": "true",
        },
    )
    print(f".env updated (project {project})")

    web_env = ROOT / "web" / ".env"
    if not web_env.exists():
        shutil.copy2(ROOT / "web" / ".env.example", web_env)
        print("web/.env <- web/.env.example (Firebase web config for this project)")


def check() -> int:
    try:
        import firebase_admin
        from firebase_admin import auth, credentials, firestore
    except ImportError:
        print(
            "firebase-admin is not installed; run .venv/bin/python scripts/setup_local.py --check",
            file=sys.stderr,
        )
        return 1

    key = load_key(KEY_PATH)
    app = firebase_admin.initialize_app(credentials.Certificate(str(KEY_PATH)))
    print(f"project:   {app.project_id}")
    print(f"account:   {key['client_email']}")

    db = firestore.client()
    users = list(db.collection("users").limit(1).stream())
    colleges = list(db.collection("colleges").limit(1).stream())
    print(f"firestore: reachable (users={len(users)} colleges={len(colleges)} sampled)")

    page = auth.list_users(max_results=1)
    print(f"auth:      reachable (users={len(page.users)} sampled)")
    print("\nFirebase looks good. Start the API and the web client:")
    print("  .venv/bin/uvicorn app.main:app --port 8080")
    print("  cd web && npm install && npm run dev")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--service-account", help="path to the downloaded service-account JSON")
    parser.add_argument("--check", action="store_true", help="verify Firestore and Auth")
    args = parser.parse_args()

    if args.check:
        if not KEY_PATH.exists():
            raise SystemExit(f"{KEY_PATH.relative_to(ROOT)} is missing; run without --check first")
        return check()

    key = install_key(args.service_account)
    configure(key)
    print("\nNext:")
    print("  .venv/bin/python scripts/setup_local.py --check")
    print("  .venv/bin/uvicorn app.main:app --port 8080")
    print("  cd web && npm install && npm run dev")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
