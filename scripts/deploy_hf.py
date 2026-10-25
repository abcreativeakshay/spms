"""Publish the API to a Hugging Face Space (Docker SDK).

Hugging Face builds whatever is in the Space repository, so this script stages a
minimal copy of the backend (``app/``, ``scripts/``, ``requirements.txt``,
``Dockerfile``) plus a Space ``README.md`` carrying the required frontmatter, and
uploads it. Nothing from ``web/``, ``tests/`` or ``secrets/`` is uploaded.

    # one-time
    pip install huggingface_hub
    hf auth login

    # deploy (creates the Space on the first run)
    python3 scripts/deploy_hf.py --space <user>/spms-api \\
        --cors https://<your-site>.netlify.app

Secrets and variables can also be set in the Space UI (Settings -> Variables and
secrets); this script only writes the ones it is given. The service-account key is
uploaded as a *secret* (write-only) when ``secrets/service-account.json`` exists,
and is never written to the staging directory or the Space repository.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SPACE_README = """---
title: SPMS API
emoji: 🎓
colorFrom: indigo
colorTo: blue
sdk: docker
app_port: 8080
pinned: false
short_description: Student Placement Management System API
---

# SPMS API

FastAPI backend for the Student Placement Management System.

- Interactive docs: [`/docs`](https://{host}/docs)
- Health probe: [`/health`](https://{host}/health)

The React client is deployed separately and calls `/api/v1`; add its origin to the
`CORS_ORIGINS` space variable.

Deployed from https://github.com/abcreativeakshay/spms by `scripts/deploy_hf.py`.
"""

STAGED_PATHS = ["app", "scripts", "requirements.txt", "Dockerfile"]

DOCKERIGNORE = """__pycache__/
*.pyc
.pytest_cache/
tests/
web/
secrets/
"""


def read_env(path: Path) -> dict[str, str]:
    """Minimal .env reader; the app itself uses pydantic-settings."""
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def stage(target: Path, host: str) -> None:
    for name in STAGED_PATHS:
        source = ROOT / name
        if not source.exists():
            raise SystemExit(f"missing {source}")
        if source.is_dir():
            shutil.copytree(source, target / name, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        else:
            shutil.copy2(source, target / name)
    (target / "README.md").write_text(SPACE_README.format(host=host))
    (target / ".dockerignore").write_text(DOCKERIGNORE)


def variable_map(env: dict[str, str], cors: str | None) -> dict[str, str]:
    return {
        "USE_FIREBASE": "true",
        "FIREBASE_PROJECT_ID": env.get("FIREBASE_PROJECT_ID", "placement-app-144e3"),
        "FIREBASE_STORAGE_BUCKET": env.get(
            "FIREBASE_STORAGE_BUCKET", "placement-app-144e3.firebasestorage.app"
        ),
        "FIRESTORE_WARM_CACHE": "true",
        "FIRESTORE_CACHE_TTL_SECONDS": env.get("FIRESTORE_CACHE_TTL_SECONDS", "30"),
        "FIREBASE_CHECK_REVOKED": "false",
        # Free Spaces give 2 vCPU to the container; one worker keeps the read cache warm
        # without every worker paying for its own Firestore round-trips.
        "WEB_CONCURRENCY": "1",
        "SEED_DEMO": "false",
        "ALLOW_DEV_TOKENS": "false",
        "CORS_ORIGINS": cors or env.get("CORS_ORIGINS", "http://localhost:5173"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--space", default="ABCREATIVEAKSHAY/spms-api", help="owner/name")
    parser.add_argument("--cors", default=None, help="comma-separated allowed origins")
    parser.add_argument(
        "--no-secrets", action="store_true", help="do not upload the local service account"
    )
    args = parser.parse_args()

    try:
        from huggingface_hub import HfApi
    except ImportError:
        print("pip install huggingface_hub", file=sys.stderr)
        return 1

    host = args.space.replace("/", "-").replace("_", "-").lower() + ".hf.space"
    env = read_env(ROOT / ".env")
    api = HfApi()

    print(f"staging backend for {args.space}")
    with tempfile.TemporaryDirectory() as tmp:
        staging = Path(tmp) / "space"
        staging.mkdir()
        stage(staging, host)
        api.create_repo(
            repo_id=args.space, repo_type="space", space_sdk="docker", exist_ok=True
        )
        api.upload_folder(
            repo_id=args.space,
            repo_type="space",
            folder_path=str(staging),
            commit_message="Deploy SPMS API",
        )

    for key, value in variable_map(env, args.cors).items():
        api.add_space_variable(repo_id=args.space, key=key, value=value)
        print(f"  variable {key}={value}")

    keyfile = ROOT / "secrets" / "service-account.json"
    if not args.no_secrets and keyfile.exists():
        api.add_space_secret(
            repo_id=args.space,
            key="GOOGLE_APPLICATION_CREDENTIALS_JSON",
            value=json.dumps(json.loads(keyfile.read_text())),
        )
        print("  secret GOOGLE_APPLICATION_CREDENTIALS_JSON=<service account>")
    else:
        print("  secret GOOGLE_APPLICATION_CREDENTIALS_JSON skipped (set it in the Space UI)")

    print(f"\nSpace:  https://huggingface.co/spaces/{args.space}")
    print(f"API:    https://{host}/api/v1")
    print(f"Health: https://{host}/health")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
