"""Cursor pagination shared by every list endpoint."""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Sequence

from app.core.config import settings
from app.core.errors import BadRequest

Filter = tuple[str, str, Any]


@dataclass
class Page:
    items: list[dict[str, Any]]
    next_cursor: str | None = None

    @property
    def has_more(self) -> bool:
        return self.next_cursor is not None


def _encode_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return {"t": "dt", "v": value.isoformat()}
    if isinstance(value, date):
        return {"t": "date", "v": value.isoformat()}
    return value


def _decode_value(value: Any) -> Any:
    if isinstance(value, dict) and "t" in value:
        if value["t"] == "dt":
            return datetime.fromisoformat(value["v"])
        if value["t"] == "date":
            return date.fromisoformat(value["v"])
    return value


def encode_cursor(value: Any, doc_id: str) -> str:
    raw = json.dumps({"v": _encode_value(value), "i": doc_id}, separators=(",", ":"))
    return base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")


def decode_cursor(cursor: str) -> tuple[Any, str]:
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        data = json.loads(base64.urlsafe_b64decode(padded.encode()))
        return _decode_value(data["v"]), data["i"]
    except Exception as exc:  # noqa: BLE001 - any malformed cursor is a 400
        raise BadRequest("Invalid pagination cursor") from exc


def clamp_limit(limit: int | None) -> int:
    if limit is None:
        return settings.default_page_limit
    return max(1, min(int(limit), settings.max_page_limit))


def paginate_items(
    items: list[dict[str, Any]],
    *,
    order_by: str,
    descending: bool = True,
    limit: int | None = None,
    cursor: str | None = None,
) -> Page:
    """Paginate an already-filtered list (used for small, scoped collections)."""
    size = clamp_limit(limit)

    def key(doc: dict[str, Any]) -> tuple[bool, Any]:
        value = doc.get(order_by)
        return (value is not None, value)

    ordered = sorted(items, key=key, reverse=descending)
    if cursor:
        start_value, start_id = decode_cursor(cursor)
        index = next((i for i, doc in enumerate(ordered) if doc["id"] == start_id), None)
        if index is None:
            ordered = [
                doc
                for doc in ordered
                if (doc.get(order_by) is not None, doc.get(order_by))
                == (start_value is not None, start_value)
                and doc["id"] != start_id
            ] or ordered
        else:
            ordered = ordered[index + 1 :]

    page_items = ordered[:size]
    next_cursor = (
        encode_cursor(page_items[-1].get(order_by), page_items[-1]["id"])
        if len(ordered) > size and page_items
        else None
    )
    return Page(items=page_items, next_cursor=next_cursor)


def paginate(
    store: Any,
    collection: str,
    filters: Sequence[Filter] = (),
    *,
    order_by: str = "createdAt",
    descending: bool = True,
    limit: int | None = None,
    cursor: str | None = None,
) -> Page:
    size = clamp_limit(limit)
    start_value: Any = None
    start_id: str | None = None
    if cursor:
        start_value, start_id = decode_cursor(cursor)

    docs = store.query(
        collection,
        list(filters),
        order_by=order_by,
        descending=descending,
        limit=size + 1,
        start_value=start_value,
        start_id=start_id,
    )
    has_more = len(docs) > size
    docs = docs[:size]
    next_cursor = (
        encode_cursor(docs[-1].get(order_by), docs[-1]["id"]) if has_more and docs else None
    )
    return Page(items=docs, next_cursor=next_cursor)
