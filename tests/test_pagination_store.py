"""Unit tests for the in-memory store and cursor pagination helpers."""

from __future__ import annotations

import pytest

from app.core.errors import BadRequest, NotFound
from app.core.pagination import (
    clamp_limit,
    decode_cursor,
    encode_cursor,
    paginate,
    paginate_items,
)
from app.repositories.store import MemoryStore


def _store() -> MemoryStore:
    store = MemoryStore()
    for index in range(1, 6):
        store.set(
            "items",
            f"doc-{index}",
            {"name": f"Item {index}", "rank": index, "tags": ["a", "b"] if index % 2 else ["c"]},
        )
    return store


# -- store ------------------------------------------------------------------ #
def test_set_get_update_merge_and_delete():
    store = MemoryStore()
    created = store.set("things", "one", {"value": 1})
    assert created == {"id": "one", "value": 1}
    assert store.get("things", "one") == {"id": "one", "value": 1}
    assert store.get("things", "missing") is None

    merged = store.set("things", "one", {"extra": True}, merge=True)
    assert merged == {"id": "one", "value": 1, "extra": True}

    replaced = store.set("things", "one", {"other": 2})
    assert replaced == {"id": "one", "other": 2}

    updated = store.update("things", "one", {"other": 3})
    assert updated["other"] == 3
    assert store.update("things", "one", {"id": "ignored"})["id"] == "one"

    with pytest.raises(NotFound):
        store.update("things", "missing", {"other": 3})

    store.delete("things", "one")
    assert store.get("things", "one") is None


def test_query_filters_ordering_limit_and_count():
    store = _store()
    assert len(store.query("items")) == 5
    assert [d["rank"] for d in store.query("items", [("rank", ">", 3)])] == [4, 5]
    assert [d["rank"] for d in store.query("items", [("rank", "<=", 2)])] == [1, 2]
    assert [d["rank"] for d in store.query("items", [("rank", "!=", 3)])] == [1, 2, 4, 5]
    assert len(store.query("items", [("rank", "in", [1, 4])])) == 2
    assert len(store.query("items", [("rank", "not_in", [1, 4])])) == 3
    assert len(store.query("items", [("tags", "array_contains", "a")])) == 3
    assert len(store.query("items", [("tags", "array_contains_any", ["b", "c"])])) == 5

    descending = store.query("items", order_by="rank", descending=True)
    assert [d["rank"] for d in descending] == [5, 4, 3, 2, 1]
    assert [d["rank"] for d in store.query("items", order_by="rank", descending=False)] == [
        1,
        2,
        3,
        4,
        5,
    ]

    assert store.count("items") == 5
    assert store.count("items", [("rank", ">", 2)]) == 3
    assert len(store.query("items", [("rank", ">", 1)], limit=2)) == 2


def test_query_start_key_semantics():
    store = _store()
    page_one = store.query("items", order_by="rank", descending=True, limit=2)
    assert [d["rank"] for d in page_one] == [5, 4]

    page_two = store.query(
        "items",
        order_by="rank",
        descending=True,
        limit=2,
        start_value=page_one[-1]["rank"],
        start_id=page_one[-1]["id"],
    )
    assert [d["rank"] for d in page_two] == [3, 2]

    # An unknown id falls back to a value comparison.
    fallback = store.query(
        "items",
        order_by="rank",
        descending=True,
        start_value=4,
        start_id="deleted-id",
    )
    assert [d["rank"] for d in fallback] == [3, 2, 1]


def test_write_batch_applies_all_operations():
    store = _store()
    store.write_batch(
        [
            ("set", "items", "doc-new", {"rank": 99, "name": "New"}),
            ("update", "items", "doc-1", {"name": "Renamed"}),
            ("delete", "items", "doc-5", None),
        ]
    )
    assert store.get("items", "doc-new")["rank"] == 99
    assert store.get("items", "doc-1")["name"] == "Renamed"
    assert store.get("items", "doc-5") is None


def test_store_returns_copies_not_references():
    store = _store()
    doc = store.get("items", "doc-1")
    doc["name"] = "mutated"
    assert store.get("items", "doc-1")["name"] == "Item 1"


# -- cursors ---------------------------------------------------------------- #
def test_cursor_round_trip_and_errors():
    cursor = encode_cursor(42, "doc-1")
    assert decode_cursor(cursor) == (42, "doc-1")

    from datetime import date, datetime, timezone

    moment = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
    assert decode_cursor(encode_cursor(moment, "doc-2")) == (moment, "doc-2")
    assert decode_cursor(encode_cursor(date(2026, 1, 2), "doc-3")) == (date(2026, 1, 2), "doc-3")

    with pytest.raises(BadRequest):
        decode_cursor("not-a-cursor")


def test_clamp_limit_defaults_and_bounds():
    assert clamp_limit(None) == 20
    assert clamp_limit(5) == 5
    assert clamp_limit(0) == 1
    assert clamp_limit(1000) == 100


def test_paginate_cursor_walks_every_page():
    store = _store()
    seen: list[str] = []
    cursor = None
    while True:
        page = paginate(store, "items", order_by="rank", descending=True, limit=2, cursor=cursor)
        seen.extend(doc["id"] for doc in page.items)
        if not page.next_cursor:
            break
        cursor = page.next_cursor
    assert seen == ["doc-5", "doc-4", "doc-3", "doc-2", "doc-1"]


def test_paginate_items_orders_and_pages():
    items = [{"id": f"i{index}", "value": index} for index in range(4)]
    page = paginate_items(items, order_by="value", descending=True, limit=2)
    assert [doc["id"] for doc in page.items] == ["i3", "i2"]
    assert page.has_more is True

    second = paginate_items(
        items, order_by="value", descending=True, limit=2, cursor=page.next_cursor
    )
    assert [doc["id"] for doc in second.items] == ["i1", "i0"]
    assert second.next_cursor is None
