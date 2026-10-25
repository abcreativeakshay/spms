"""FirestoreStore query translation (no credentials required)."""

from __future__ import annotations

from app.repositories.store import FirestoreStore


class _FakeQuery:
    def __init__(self) -> None:
        self.filters: list[object] = []

    def where(self, filter):  # noqa: A002 - matches the Firestore client signature
        self.filters.append(filter)
        return self


class _FakeCollection:
    def __init__(self) -> None:
        self.query = _FakeQuery()

    def where(self, filter):  # noqa: A002 - matches the Firestore client signature
        self.query.filters.append(filter)
        return self.query


class _FakeClient:
    def __init__(self) -> None:
        self.collection_ref = _FakeCollection()

    def collection(self, name: str) -> _FakeCollection:
        return self.collection_ref


def _translate(op: str) -> str:
    store = FirestoreStore(_FakeClient())
    query = store._build_query("students", [("field", op, "value")])
    return query.filters[0].op_string


def test_array_operators_use_firestore_hyphen_syntax():
    assert _translate("array_contains") == "array-contains"
    assert _translate("array_contains_any") == "array-contains-any"


def test_scalar_operators_pass_through():
    assert _translate("==") == "=="
    assert _translate(">=") == ">="
    assert _translate("in") == "in"
    assert _translate("not_in") == "not-in"
