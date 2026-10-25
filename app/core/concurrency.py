"""Concurrency helpers for blocking I/O.

Firestore calls are network I/O. A screen that needs several independent reads
should issue them together instead of paying their latencies one after another.
Services fan out on this small pool; the Firestore client is thread-safe.
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable

logger = logging.getLogger("spms")

_pool = ThreadPoolExecutor(max_workers=8, thread_name_prefix="spms-io")


def gather(*calls: Callable[[], Any]) -> list[Any]:
    """Run ``calls`` concurrently and return their results in order.

    Exceptions are re-raised from the first failing call. Do not call this from
    inside a task already running on this pool.
    """
    futures = [_pool.submit(call) for call in calls]
    return [future.result() for future in futures]


def submit(call: Callable[[], Any]) -> None:
    """Fire-and-forget a call; failures are logged instead of raised."""
    _pool.submit(_run_logged, call)


def _run_logged(call: Callable[[], Any]) -> Any:
    try:
        return call()
    except Exception:  # noqa: BLE001 - background work must not crash a request
        logger.exception("Background task failed")
        return None
