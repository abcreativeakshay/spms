"""Read-through cache behaviour of ``FirestoreStore`` (no credentials needed)."""

from __future__ import annotations

import time
from typing import Any

from app.core.warm import warm_caches
from app.repositories.store import FirestoreStore, MemoryStore


class _Snapshot:
    def __init__(self, doc_id: str, data: dict[str, Any] | None) -> None:
        self.id = doc_id
        self._data = data
        self.exists = data is not None

    def to_dict(self) -> dict[str, Any] | None:
        return dict(self._data) if self._data is not None else None


class _DocRef:
    def __init__(self, client: "_Client", collection: str, doc_id: str) -> None:
        self.client = client
        self.collection = collection
        self.doc_id = doc_id

    def get(self) -> _Snapshot:
        self.client.reads += 1
        return _Snapshot(self.doc_id, self.client.data.get((self.collection, self.doc_id)))

    def set(self, payload: dict[str, Any], merge: bool = False) -> None:
        self.client.writes += 1
        key = (self.collection, self.doc_id)
        merged = {**self.client.data.get(key, {}), **payload} if merge else payload
        self.client.data[key] = merged

    def update(self, payload: dict[str, Any]) -> None:
        self.client.writes += 1
        key = (self.collection, self.doc_id)
        self.client.data[key] = {**self.client.data.get(key, {}), **payload}

    def delete(self) -> None:
        self.client.writes += 1
        self.client.data.pop((self.collection, self.doc_id), None)


class _Collection:
    def __init__(self, client: "_Client", name: str) -> None:
        self.client = client
        self.name = name

    def document(self, doc_id: str) -> _DocRef:
        return _DocRef(self.client, self.name, doc_id)


class _Client:
    def __init__(self) -> None:
        self.data: dict[tuple[str, str], dict[str, Any]] = {("users", "u1"): {"name": "Ada"}}
        self.reads = 0
        self.writes = 0

    def collection(self, name: str) -> _Collection:
        return _Collection(self, name)


def test_repeated_gets_are_served_from_cache():
    client = _Client()
    store = FirestoreStore(client, cache_ttl=30)

    first = store.get("users", "u1")
    second = store.get("users", "u1")

    assert first == {"id": "u1", "name": "Ada"}
    assert second == first
    assert client.reads == 1
    # Callers may mutate what they receive without poisoning the cache.
    second["name"] = "mutated"
    assert store.get("users", "u1")["name"] == "Ada"


def test_writes_invalidate_the_cached_collection():
    client = _Client()
    store = FirestoreStore(client, cache_ttl=30)

    store.get("users", "u1")
    store.update("users", "u1", {"name": "Grace"})

    assert store.get("users", "u1")["name"] == "Grace"
    assert client.writes == 1
    # update() re-reads once to return the merged document, then the read is cached.
    reads_after_update = client.reads
    store.get("users", "u1")
    assert client.reads == reads_after_update


def test_ttl_of_zero_disables_the_cache():
    client = _Client()
    store = FirestoreStore(client, cache_ttl=0)

    store.get("users", "u1")
    store.get("users", "u1")

    assert client.reads == 2
    assert store.cache_enabled is False


def test_stale_entries_are_served_while_one_refresh_runs():
    client = _Client()
    store = FirestoreStore(client, cache_ttl=0.01)

    store.get("users", "u1")
    assert client.reads == 1

    time.sleep(0.02)
    stale = store.get("users", "u1")  # returns immediately, refreshes in background
    assert stale == {"id": "u1", "name": "Ada"}

    deadline = time.monotonic() + 2
    while client.reads < 2 and time.monotonic() < deadline:
        time.sleep(0.005)
    assert client.reads >= 2

    # Once refreshed, reads are served from the cache again.
    reads = client.reads
    assert store.get("users", "u1") == {"id": "u1", "name": "Ada"}
    assert client.reads == reads


def test_warm_up_is_a_noop_without_a_firestore_store():
    warm_caches(MemoryStore())


def test_counts_by_groups_values_in_memory():
    store = MemoryStore()
    for index, college in enumerate(["c1", "c1", "c2", "c3"]):
        store.set("students", f"s{index}", {"collegeId": college})

    assert store.counts_by("students", "collegeId", ["c1", "c2", "missing"]) == {
        "c1": 2,
        "c2": 1,
        "missing": 0,
    }
