"""Post-change live verification: bulk counters, drive stats, analytics.

Credentials come from the environment, never from this file:

    SPMS_API_KEY, SPMS_ADMIN_EMAIL, SPMS_ADMIN_PASSWORD,
    SPMS_STUDENT_EMAIL, SPMS_STUDENT_PASSWORD
"""

from __future__ import annotations

import json
import os
import statistics
import time
import urllib.request

BASE = os.environ.get("SPMS_API_BASE", "http://127.0.0.1:8080/api/v1")


def post(url: str, payload: dict) -> dict:
    request = urllib.request.Request(
        url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(request) as response:
        return json.load(response)


def token(email: str, password: str) -> str:
    key = os.environ["SPMS_API_KEY"]
    return post(
        f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={key}",
        {"email": email, "password": password, "returnSecureToken": True},
    )["idToken"]


def get(path: str, auth: str) -> dict:
    request = urllib.request.Request(f"{BASE}/{path}", headers={"Authorization": f"Bearer {auth}"})
    with urllib.request.urlopen(request) as response:
        return json.load(response)


def timed(path: str, auth: str) -> float:
    started = time.perf_counter()
    get(path, auth)
    return (time.perf_counter() - started) * 1000


def main() -> None:
    admin = token(os.environ["SPMS_ADMIN_EMAIL"], os.environ["SPMS_ADMIN_PASSWORD"])
    student = token(os.environ["SPMS_STUDENT_EMAIL"], os.environ["SPMS_STUDENT_PASSWORD"])

    print("== latency")
    for path in (
        "auth/me",
        "colleges",
        "companies",
        "drives",
        "students",
        "applications?limit=10",
        "notifications?limit=10",
        "analytics/placements",
    ):
        first = timed(path, admin)
        warm = statistics.median([timed(path, admin) for _ in range(3)])
        print(f"  {path:28s} first {first:7.0f} ms  warm {warm:6.1f} ms")

    print("== payload checks")
    colleges = get("colleges", admin)["items"]
    print("  colleges:", [(c["name"], c.get("studentCount"), c.get("batchCount")) for c in colleges])

    companies = get("companies", admin)["items"]
    print("  companies:", [(c["name"], c.get("driveCount")) for c in companies])

    drives = get("drives?limit=100", admin)["items"]
    print("  drives:", [(d["role"], d.get("stats")) for d in drives])

    placements = get("analytics/placements", admin)
    print(
        "  placements:",
        {
            "students": placements.get("totalStudents"),
            "placed": placements.get("placedStudents"),
            "byCollege": placements.get("byCollege"),
        },
    )

    student_drives = get("drives?limit=5", student)["items"]
    print(
        "  student drives:",
        [
            {
                "role": d["role"],
                "applied": d.get("application") is not None,
                "eligible": (d.get("eligibilityResult") or {}).get("eligible"),
            }
            for d in student_drives
        ],
    )


if __name__ == "__main__":
    main()
