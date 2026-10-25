"""Publish the React client to a Hugging Face *static* Space.

Static Spaces are free; Docker Spaces (needed for the Python API) require a PRO
subscription. This script builds ``web/`` locally — so the Firebase web config in
``web/.env`` is baked in — and uploads ``dist/`` to the Space repository.

    python3 scripts/deploy_hf_web.py --space <user>/spms-web \\
        --api-base https://<user>-spms-api.hf.space/api/v1

``VITE_API_BASE_URL`` must be the deployed API, including ``/api/v1``: Vite inlines it
at build time, so re-run this script whenever the API URL changes.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"

SPACE_README = """---
title: SPMS
emoji: 🎓
colorFrom: gray
colorTo: indigo
sdk: static
pinned: false
short_description: Student Placement Management System
---

# SPMS

Student Placement Management System client. The FastAPI backend is deployed separately;
this build calls `{api_base}`.

Deployed from https://github.com/abcreativeakshay/spms by `scripts/deploy_hf_web.py`.
"""


def build(api_base: str) -> Path:
    env = {**os.environ, "VITE_API_BASE_URL": api_base}
    if not (WEB / "node_modules").exists():
        subprocess.run(["npm", "ci"], cwd=WEB, env=env, check=True)
    subprocess.run(["npm", "run", "build"], cwd=WEB, env=env, check=True)
    dist = WEB / "dist"
    if not (dist / "index.html").exists():
        raise SystemExit(f"build produced no index.html in {dist}")
    return dist


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--space", default="ABCREATIVEAKSHAY/spms-web", help="owner/name")
    parser.add_argument("--api-base", required=True, help="deployed API base, e.g. https://x.hf.space/api/v1")
    parser.add_argument("--skip-build", action="store_true", help="upload the existing web/dist")
    args = parser.parse_args()

    try:
        from huggingface_hub import HfApi
    except ImportError:
        print("pip install huggingface_hub", file=sys.stderr)
        return 1

    dist = WEB / "dist" if args.skip_build else build(args.api_base)
    print(f"uploading {dist} to {args.space}")

    with tempfile.TemporaryDirectory() as tmp:
        staging = Path(tmp) / "space"
        shutil.copytree(dist, staging)
        (staging / "README.md").write_text(SPACE_README.format(api_base=args.api_base))
        # Static Spaces have no rewrite rules; serve the SPA shell for unknown paths.
        shutil.copy2(staging / "index.html", staging / "404.html")

        api = HfApi()
        api.create_repo(
            repo_id=args.space, repo_type="space", space_sdk="static", exist_ok=True
        )
        api.upload_folder(
            repo_id=args.space,
            repo_type="space",
            folder_path=str(staging),
            commit_message="Deploy SPMS client",
            delete_patterns=["*"],  # drop files from previous builds
        )

    host = args.space.replace("/", "-").replace("_", "-").lower() + ".hf.space"
    print(f"\nSpace: https://huggingface.co/spaces/{args.space}")
    print(f"Site:  https://{host}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
