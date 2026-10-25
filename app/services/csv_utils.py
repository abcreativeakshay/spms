"""CSV parsing helpers for bulk imports."""

from __future__ import annotations

import csv
import io
import re

from app.core.errors import BadRequest

_HEADER_CLEAN = re.compile(r"[^a-z0-9]")


def normalize_header(name: str) -> str:
    return _HEADER_CLEAN.sub("", (name or "").strip().lower())


def parse_csv(data: bytes, *, required: set[str], max_rows: int = 500) -> list[dict[str, str]]:
    """Decode, normalize headers and enforce required columns.

    Headers are matched case/punctuation-insensitively (`College ID` == `collegeId`).
    """
    if not data:
        raise BadRequest("CSV file is empty")
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise BadRequest("CSV must be UTF-8 encoded") from exc

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise BadRequest("CSV has no header row")

    mapping = {field: normalize_header(field) for field in reader.fieldnames}
    normalized_required = {normalize_header(r) for r in required}
    present = set(mapping.values())
    missing = normalized_required - present
    if missing:
        raise BadRequest(f"CSV missing required columns: {', '.join(sorted(missing))}")

    rows: list[dict[str, str]] = []
    for raw in reader:
        if len(rows) >= max_rows:
            raise BadRequest(f"CSV exceeds the {max_rows} row limit per import")
        row = {
            mapping[key]: (value or "").strip()
            for key, value in raw.items()
            if key in mapping and value is not None
        }
        if not any(row.values()):
            continue
        rows.append(row)
    if not rows:
        raise BadRequest("CSV contains no data rows")
    return rows


def split_list(value: str | None, *, separators: str = ";|,") -> list[str]:
    if not value:
        return []
    pattern = f"[{re.escape(separators)}]"
    return [part.strip() for part in re.split(pattern, value) if part.strip()]


def parse_float(value: str | None, field: str, *, required: bool = False) -> float | None:
    if not value:
        if required:
            raise ValueError(f"{field} is required")
        return None
    try:
        return float(value)
    except ValueError as exc:
        raise ValueError(f"{field} must be a number") from exc


def parse_int(value: str | None, field: str, *, required: bool = False) -> int | None:
    if not value:
        if required:
            raise ValueError(f"{field} is required")
        return None
    try:
        return int(float(value))
    except ValueError as exc:
        raise ValueError(f"{field} must be an integer") from exc
