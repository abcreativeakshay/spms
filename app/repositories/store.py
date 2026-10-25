"""Storage abstraction: one interface, two backends.

* ``FirestoreStore`` — production (and emulator) via firebase-admin
* ``MemoryStore``    — tests / local dev, no credentials required

Repositories and services only ever see ``DocumentStore``. Documents returned
from the store always include their ``id``.
"""

from __future__ import annotations

import copy
import threading
import uuid
from collections import defaultdict
from functools import lru_cache
from typing import Any, Literal, Protocol, Sequence

Filter = tuple[str, str, Any]
WriteOp = tuple[str, str, str | None, dict[str, Any] | None]  # (op, collection, id, data)

_ARRAY_OPS = {"array_contains", "array_contains_any"}
_NEGATIVE_OPS = {"!=", "not_in"}


class DocumentStore(Protocol):
    def new_id(self) -> str: ...

    def get(self, collection: str, doc_id: str) -> dict[str, Any] | None: ...

    def set(
        self, collection: str, doc_id: str, data: dict[str, Any], *, merge: bool = False
    ) -> dict[str, Any]: ...

    def update(self, collection: str, doc_id: str, patch: dict[str, Any]) -> dict[str, Any]: ...

    def delete(self, collection: str, doc_id: str) -> None: ...

    def query(
        self,
        collection: str,
        filters: Sequence[Filter] = (),
        *,
        order_by: str | None = None,
        descending: bool = True,
        limit: int | None = None,
        start_value: Any = None,
        start_id: str | None = None,
    ) -> list[dict[str, Any]]: ...

    def count(self, collection: str, filters: Sequence[Filter] = ()) -> int: ...

    def write_batch(self, ops: Sequence[WriteOp]) -> None: ...


# --------------------------------------------------------------------------- #
# In-memory backend
# --------------------------------------------------------------------------- #
def _matches(doc: dict[str, Any], filters: Sequence[Filter]) -> bool:
    for field, op, value in filters:
        actual = doc.get(field)
        if op == "==":
            if actual != value:
                return False
        elif op == "!=":
            if actual == value:
                return False
        elif op == "in":
            if actual not in (value or []):
                return False
        elif op == "not_in":
            if actual in (value or []):
                return False
        elif op == ">":
            if actual is None or not actual > value:
                return False
        elif op == ">=":
            if actual is None or not actual >= value:
                return False
        elif op == "<":
            if actual is None or not actual < value:
                return False
        elif op == "<=":
            if actual is None or not actual <= value:
                return False
        elif op == "array_contains":
            if value not in (actual or []):
                return False
        elif op == "array_contains_any":
            if not set(value or []).intersection(actual or []):
                return False
        else:  # pragma: no cover - guard against typos
            raise ValueError(f"Unsupported filter operator: {op}")
    return True


def _sort_key(doc: dict[str, Any], order_by: str) -> tuple[Any, str]:
    value = doc.get(order_by)
    # None sorts before real values; the id is a deterministic tiebreaker.
    return (value is not None, value, doc["id"])


class MemoryStore:
    def __init__(self) -> None:
        self._data: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
        self._lock = threading.RLock()

    def reset(self) -> None:
        with self._lock:
            self._data.clear()

    def new_id(self) -> str:
        return uuid.uuid4().hex

    def get(self, collection: str, doc_id: str) -> dict[str, Any] | None:
        with self._lock:
            doc = self._data[collection].get(doc_id)
            return {"id": doc_id, **copy.deepcopy(doc)} if doc is not None else None

    def set(
        self, collection: str, doc_id: str, data: dict[str, Any], *, merge: bool = False
    ) -> dict[str, Any]:
        with self._lock:
            payload = {k: v for k, v in data.items() if k != "id"}
            if merge and doc_id in self._data[collection]:
                payload = {**self._data[collection][doc_id], **payload}
            self._data[collection][doc_id] = copy.deepcopy(payload)
            return {"id": doc_id, **copy.deepcopy(payload)}

    def update(self, collection: str, doc_id: str, patch: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            existing = self._data[collection].get(doc_id)
            if existing is None:
                from app.core.errors import NotFound

                raise NotFound(f"{collection}/{doc_id} not found")
            existing.update({k: v for k, v in patch.items() if k != "id"})
            return {"id": doc_id, **copy.deepcopy(existing)}

    def delete(self, collection: str, doc_id: str) -> None:
        with self._lock:
            self._data[collection].pop(doc_id, None)

    def query(
        self,
        collection: str,
        filters: Sequence[Filter] = (),
        *,
        order_by: str | None = None,
        descending: bool = True,
        limit: int | None = None,
        start_value: Any = None,
        start_id: str | None = None,
    ) -> list[dict[str, Any]]:
        with self._lock:
            docs = [
                {"id": doc_id, **copy.deepcopy(doc)}
                for doc_id, doc in self._data[collection].items()
                if _matches(doc, filters)
            ]
        if order_by:
            docs.sort(key=lambda d: _sort_key(d, order_by), reverse=descending)
        if start_id:
            index = next((i for i, d in enumerate(docs) if d["id"] == start_id), None)
            if index is not None:
                docs = docs[index + 1 :]
            else:
                start_key = (start_value is not None, start_value, start_id)
                docs = [
                    d
                    for d in docs
                    if (_sort_key(d, order_by) > start_key) != descending
                    and d["id"] != start_id
                ]
        if limit is not None:
            docs = docs[:limit]
        return docs

    def count(self, collection: str, filters: Sequence[Filter] = ()) -> int:
        with self._lock:
            return sum(1 for doc in self._data[collection].values() if _matches(doc, filters))

    def write_batch(self, ops: Sequence[WriteOp]) -> None:
        for op, collection, doc_id, data in ops:
            if op == "delete":
                self.delete(collection, doc_id)  # type: ignore[arg-type]
            elif op == "update":
                self.update(collection, doc_id, data or {})  # type: ignore[arg-type]
            else:
                self.set(collection, doc_id, data or {})  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# Firestore backend
# --------------------------------------------------------------------------- #
class FirestoreStore:
    def __init__(self, client: Any) -> None:
        self._client = client

    def new_id(self) -> str:
        return self._client.collection("_ids").document().id

    def _ref(self, collection: str, doc_id: str) -> Any:
        return self._client.collection(collection).document(doc_id)

    def get(self, collection: str, doc_id: str) -> dict[str, Any] | None:
        snapshot = self._ref(collection, doc_id).get()
        if not snapshot.exists:
            return None
        return {"id": snapshot.id, **(snapshot.to_dict() or {})}

    def set(
        self, collection: str, doc_id: str, data: dict[str, Any], *, merge: bool = False
    ) -> dict[str, Any]:
        payload = {k: v for k, v in data.items() if k != "id"}
        self._ref(collection, doc_id).set(payload, merge=merge)
        return {"id": doc_id, **payload}

    def update(self, collection: str, doc_id: str, patch: dict[str, Any]) -> dict[str, Any]:
        from app.core.errors import NotFound
        from google.cloud.firestore_v1 import NotFound as FirestoreNotFound

        payload = {k: v for k, v in patch.items() if k != "id"}
        try:
            self._ref(collection, doc_id).update(payload)
        except FirestoreNotFound as exc:
            raise NotFound(f"{collection}/{doc_id} not found") from exc
        snapshot = self._ref(collection, doc_id).get()
        return {"id": doc_id, **(snapshot.to_dict() or {})}

    def delete(self, collection: str, doc_id: str) -> None:
        self._ref(collection, doc_id).delete()

    def _build_query(self, collection: str, filters: Sequence[Filter]) -> Any:
        from google.cloud.firestore_v1.base_query import FieldFilter

        query = self._client.collection(collection)
        for field, op, value in filters:
            firestore_op = {**{o: o for o in ["==", "!=", "in", "not_in", ">", ">=", "<", "<="]},
                            "not_in": "not-in",
                            "array_contains": "array_contains",
                            "array_contains_any": "array_contains_any"}.get(op, op)
            query = query.where(filter=FieldFilter(field, firestore_op, value))
        return query

    def query(
        self,
        collection: str,
        filters: Sequence[Filter] = (),
        *,
        order_by: str | None = None,
        descending: bool = True,
        limit: int | None = None,
        start_value: Any = None,
        start_id: str | None = None,
    ) -> list[dict[str, Any]]:
        from google.cloud.firestore_v1.base_query import Query

        query = self._build_query(collection, filters)
        direction = Query.DESCENDING if descending else Query.ASCENDING
        if order_by:
            query = query.order_by(order_by, direction=direction)
            # Stable tiebreaker; start_after needs both key parts.
            query = query.order_by("__name__", direction=direction)
            if start_id:
                query = query.start_after([start_value, self._ref(collection, start_id)])
        if limit is not None:
            query = query.limit(limit)
        return [
            {"id": snap.id, **(snap.to_dict() or {})}
            for snap in query.stream()
        ]

    def count(self, collection: str, filters: Sequence[Filter] = ()) -> int:
        query = self._build_query(collection, filters)
        result = query.count(alias="total").get()
        return int(result[0][0].value)

    def write_batch(self, ops: Sequence[WriteOp]) -> None:
        from google.cloud import firestore as firestore_module

        batch = self._client.batch()
        for op, collection, doc_id, data in ops:
            ref = self._ref(collection, doc_id)  # type: ignore[arg-type]
            if op == "delete":
                batch.delete(ref)
            elif op == "update":
                batch.update(ref, data or {})
            else:
                batch.set(ref, data or {})
        batch.commit()


# --------------------------------------------------------------------------- #
# Dependency
# --------------------------------------------------------------------------- #
@lru_cache
def get_store() -> DocumentStore:
    from app.core.config import settings

    if settings.use_firebase:
        from app.core.firebase import get_firestore_client

        return FirestoreStore(get_firestore_client())
    return MemoryStore()
