"""Behavior tests for PgVectorMemoryStore: SQL args, row mapping, error mapping, connect.

The DB layer is a canned-row fake (the asyncpg analog of httpx.MockTransport), with no Postgres,
no network. The behavioral contract against real pgvector is test_store_live.py.
"""

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime

import asyncpg
import pytest

from cortex_core import MemoryRecord, MemoryStoreError
from cortex_memory import PgVectorMemoryStore

_AT = datetime(2026, 7, 3, 12, 0, 0, tzinfo=UTC)


class FakeDatabase:
    """A Database that records calls and returns canned rows (or raises a canned error)."""

    def __init__(
        self, rows: Sequence[Mapping[str, object]] = (), *, fail: Exception | None = None
    ) -> None:
        self._rows = rows
        self._fail = fail
        self.calls: list[tuple[str, tuple[object, ...]]] = []
        self.closed = False

    async def execute(self, sql: str, /, *args: object) -> object:
        if self._fail is not None:
            raise self._fail
        self.calls.append((sql, args))
        return "INSERT 0 1"

    async def fetch(self, sql: str, /, *args: object) -> Sequence[Mapping[str, object]]:
        if self._fail is not None:
            raise self._fail
        self.calls.append((sql, args))
        return self._rows

    async def close(self) -> None:
        if self._fail is not None:
            raise self._fail
        self.closed = True


def _record() -> MemoryRecord:
    return MemoryRecord(id="m-1", text="hi", embedding=(1.0, 0.5), at=_AT)


async def test_add_executes_insert_with_a_vector_literal() -> None:
    db = FakeDatabase()
    await PgVectorMemoryStore(db).add(_record())
    sql, args = db.calls[0]
    assert "INSERT INTO memories" in sql
    assert args == ("m-1", "hi", "[1.0,0.5]", _AT)


async def test_add_wraps_a_backend_error() -> None:
    db = FakeDatabase(fail=asyncpg.PostgresError("boom"))
    with pytest.raises(MemoryStoreError, match="adding memory 'm-1'") as excinfo:
        await PgVectorMemoryStore(db).add(_record())
    assert isinstance(excinfo.value.__cause__, asyncpg.PostgresError)


async def test_search_maps_rows_to_scored_memories_and_sends_the_query() -> None:
    rows: list[dict[str, object]] = [
        {"id": "a", "text": "alpha", "embedding": "[1,0]", "created_at": _AT, "score": 0.9},
        {"id": "b", "text": "beta", "embedding": "[0,1]", "created_at": _AT, "score": 0.1},
    ]
    db = FakeDatabase(rows=rows)
    hits = await PgVectorMemoryStore(db).search((1.0, 0.0), k=5)
    assert [hit.record.id for hit in hits] == ["a", "b"]
    assert hits[0].record.embedding == (1.0, 0.0)
    assert hits[0].score == 0.9
    sql, args = db.calls[0]
    assert "ORDER BY embedding <=>" in sql
    assert args == ("[1.0,0.0]", 5)


async def test_empty_search_returns_nothing() -> None:
    assert await PgVectorMemoryStore(FakeDatabase()).search((1.0,), k=5) == ()


async def test_search_wraps_a_backend_error() -> None:
    db = FakeDatabase(fail=asyncpg.InterfaceError("pool is closing"))
    with pytest.raises(MemoryStoreError, match="search failed") as excinfo:
        await PgVectorMemoryStore(db).search((1.0,), k=1)
    assert isinstance(excinfo.value.__cause__, asyncpg.InterfaceError)


async def test_search_wraps_a_malformed_row() -> None:
    rows: list[dict[str, object]] = [{"id": "a", "text": "alpha"}]  # missing embedding/score/at
    with pytest.raises(MemoryStoreError, match="malformed memory row"):
        await PgVectorMemoryStore(FakeDatabase(rows=rows)).search((1.0,), k=1)


async def test_aclose_closes_the_pool() -> None:
    db = FakeDatabase()
    await PgVectorMemoryStore(db).aclose()
    assert db.closed is True


async def test_aclose_wraps_a_backend_error() -> None:
    db = FakeDatabase(fail=asyncpg.PostgresError("cannot close"))
    with pytest.raises(MemoryStoreError, match="closing the memory store"):
        await PgVectorMemoryStore(db).aclose()


async def test_connect_builds_a_store_owning_a_fresh_pool(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_pool = FakeDatabase()
    seen: list[str] = []

    async def fake_create_pool(dsn: str) -> FakeDatabase:
        seen.append(dsn)
        return fake_pool

    monkeypatch.setattr(asyncpg, "create_pool", fake_create_pool)
    store = await PgVectorMemoryStore.connect("postgresql://cortex@localhost/cortex")
    await store.add(_record())
    assert seen == ["postgresql://cortex@localhost/cortex"]
    assert fake_pool.calls  # the store issued its INSERT through the created pool
