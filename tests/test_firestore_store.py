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


def _build(op: str):
    store = FirestoreStore(_FakeClient())
    query = store._build_query("students", [("field", op, ["value"] if "array" in op else "value")])
    return query.filters[0]


def _translate(op: str) -> str:
    return _build(op).op_string


def test_array_operators_use_firestore_proto_names():
    assert _translate("array_contains") == "array_contains"
    assert _translate("array_contains_any") == "array_contains_any"
    # The client validates operators when serialising the filter, so make sure
    # the generated filters really can be sent to Firestore.
    _build("array_contains")._to_pb()
    _build("array_contains_any")._to_pb()


def test_scalar_operators_pass_through():
    assert _translate("==") == "=="
    assert _translate(">=") == ">="
    assert _translate("in") == "in"
    assert _translate("not_in") == "not-in"
    _build("not_in")._to_pb()
