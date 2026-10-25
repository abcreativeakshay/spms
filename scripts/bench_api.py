"""Time the endpoints each screen calls.

Usage (Firebase mode):

    SPMS_API_KEY=<web-api-key> SPMS_EMAIL=admin@example.com \\
    SPMS_PASSWORD=<password> .venv/bin/python scripts/bench_api.py

Usage (memory/dev tokens):

    SPMS_DEV_TOKEN=dev:demo-admin .venv/bin/python scripts/bench_api.py

Each endpoint is called twice: the first call is a cold read, the second shows
what a repeat visit costs once the server-side read cache is warm.
"""

from __future__ import annotations

import json
import os
import statistics
import time
import urllib.request

BASE = os.environ.get("SPMS_API_BASE", "http://127.0.0.1:8080/api/v1")
ENDPOINTS = [
    "auth/me",
    "colleges",
    "companies",
    "drives",
    "students",
    "applications?limit=10",
    "notifications?limit=10",
    "analytics/placements",
]


def _post_json(url: str, payload: dict) -> dict:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request) as response:
        return json.load(response)


def id_token() -> str:
    dev_token = os.environ.get("SPMS_DEV_TOKEN")
    if dev_token:
        return dev_token
    api_key = os.environ["SPMS_API_KEY"]
    payload = _post_json(
        f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={api_key}",
        {
            "email": os.environ["SPMS_EMAIL"],
            "password": os.environ["SPMS_PASSWORD"],
            "returnSecureToken": True,
        },
    )
    return payload["idToken"]


def timed(path: str, token: str) -> float:
    request = urllib.request.Request(
        f"{BASE}/{path}", headers={"Authorization": f"Bearer {token}"}
    )
    started = time.perf_counter()
    with urllib.request.urlopen(request) as response:
        response.read()
    return (time.perf_counter() - started) * 1000


def main() -> None:
    token = id_token()
    print(f"{'endpoint':28s} {'cold ms':>9s} {'warm ms':>9s}")
    cold_times: list[float] = []
    warm_times: list[float] = []
    for path in ENDPOINTS:
        cold = timed(path, token)
        warm = statistics.median([timed(path, token) for _ in range(3)])
        cold_times.append(cold)
        warm_times.append(warm)
        print(f"{path:28s} {cold:9.0f} {warm:9.0f}")
    print(
        f"{'median':28s} {statistics.median(cold_times):9.0f} "
        f"{statistics.median(warm_times):9.0f}"
    )


if __name__ == "__main__":
    main()
