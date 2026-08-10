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
        self,
        rows: Sequence[Mapping[str, object]] = (),
        *,
        fail: Exception | None = None,
        status: str = "INSERT 0 1",
    ) -> None:
        self._rows = rows
        self._fail = fail
        self._status = status
        self.calls: list[tuple[str, tuple[object, ...]]] = []
        self.closed = False

    async def execute(self, sql: str, /, *args: object) -> object:
        if self._fail is not None:
            raise self._fail
        self.calls.append((sql, args))
        return self._status

    async def fetch(self, sql: str, /, *args: object) -> Sequence[Mapping[str, object]]:
        if self._fail is not None:
            raise self._fail
        self.calls.append((sql, args))
        return self._rows

    async def close(self) -> None:
        if self._fail is not None:
            raise self._fail
        self.closed = True


def _record(*, scope: str = "global", tainted: bool = False) -> MemoryRecord:
    return MemoryRecord(
        id="m-1", text="hi", embedding=(1.0, 0.5), at=_AT, scope=scope, tainted=tainted
    )


async def test_add_executes_insert_with_a_vector_literal_scope_and_taint() -> None:
    db = FakeDatabase()
    await PgVectorMemoryStore(db).add(_record(scope="work", tainted=True))
    sql, args = db.calls[0]
    assert "INSERT INTO memories" in sql
    assert "scope" in sql
    assert "tainted" in sql
    # id, text, vector literal, scope, tainted, created_at appear in column order (ADR-0019).
    assert args == ("m-1", "hi", "[1.0,0.5]", "work", True, _AT)


async def test_add_wraps_a_backend_error() -> None:
    db = FakeDatabase(fail=asyncpg.PostgresError("boom"))
    with pytest.raises(MemoryStoreError, match="adding memory 'm-1'") as excinfo:
        await PgVectorMemoryStore(db).add(_record())
    assert isinstance(excinfo.value.__cause__, asyncpg.PostgresError)


async def test_search_maps_rows_to_scored_memories_and_sends_the_query() -> None:
    rows: list[dict[str, object]] = [
        {
            "id": "a",
            "text": "alpha",
            "embedding": "[1,0]",
            "scope": "work",
            "tainted": False,
            "created_at": _AT,
            "score": 0.9,
        },
        {
            "id": "b",
            "text": "beta",
            "embedding": "[0,1]",
            "scope": "global",
            "tainted": True,
            "created_at": _AT,
            "score": 0.1,
        },
    ]
    db = FakeDatabase(rows=rows)
    hits = await PgVectorMemoryStore(db).search((1.0, 0.0), k=5)
    assert [hit.record.id for hit in hits] == ["a", "b"]
    assert hits[0].record.embedding == (1.0, 0.0)
    assert hits[0].record.scope == "work"  # the namespace roundtrips out of the row
    assert (hits[0].record.tainted, hits[1].record.tainted) == (False, True)  # marker roundtrips
    assert hits[0].score == 0.9
    sql, args = db.calls[0]
    assert "ORDER BY embedding <=>" in sql
    assert "tainted" in sql  # the marker is selected back
    assert "WHERE scope" not in sql  # unscoped search ranks over every memory
    assert args == ("[1.0,0.0]", 5)


async def test_scoped_search_filters_by_any_of_the_requested_scopes() -> None:
    db = FakeDatabase(rows=())
    await PgVectorMemoryStore(db).search((1.0, 0.0), k=3, scopes=["conv-a", "conv-b"])
    sql, args = db.calls[0]
    assert "WHERE scope = ANY($3)" in sql
    assert args == ("[1.0,0.0]", 3, ["conv-a", "conv-b"])


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


async def test_count_candidates_asks_the_server_for_a_count_over_every_memory() -> None:
    db = FakeDatabase(rows=[{"total": 4213}])
    assert await PgVectorMemoryStore(db).count_candidates() == 4213
    sql, args = db.calls[0]
    assert sql == "SELECT count(*) AS total FROM memories"  # the server counts, not this adapter
    assert args == ()  # no k, because the count is deliberately not bounded by the pool's width
    assert "LIMIT" not in sql  # nor capped: the whole candidate set or nothing


async def test_count_candidates_filters_by_the_same_scopes_search_would() -> None:
    db = FakeDatabase(rows=[{"total": 7}])
    assert await PgVectorMemoryStore(db).count_candidates(scopes=["conv-a", "conv-b"]) == 7
    sql, args = db.calls[0]
    assert sql == "SELECT count(*) AS total FROM memories WHERE scope = ANY($1)"
    assert args == (["conv-a", "conv-b"],)


async def test_count_candidates_wraps_a_backend_error() -> None:
    db = FakeDatabase(fail=asyncpg.PostgresError("boom"))
    with pytest.raises(MemoryStoreError, match="counting memory candidates failed") as excinfo:
        await PgVectorMemoryStore(db).count_candidates()
    assert isinstance(excinfo.value.__cause__, asyncpg.PostgresError)


@pytest.mark.parametrize(
    "rows", [[], [{"rows": 3}], [{"total": "not-a-number"}]], ids=["none", "unnamed", "unparsable"]
)
async def test_count_candidates_wraps_a_malformed_reply(rows: list[dict[str, object]]) -> None:
    """An aggregate always answers with one named integer; anything else is a broken contract."""
    with pytest.raises(MemoryStoreError, match="malformed count") as excinfo:
        await PgVectorMemoryStore(FakeDatabase(rows=rows)).count_candidates()
    assert isinstance(excinfo.value.__cause__, KeyError | IndexError | ValueError)


async def test_delete_scope_executes_delete_and_returns_the_row_count() -> None:
    db = FakeDatabase(status="DELETE 3")
    removed = await PgVectorMemoryStore(db).delete_scope("conv-a")
    assert removed == 3  # the count parsed out of asyncpg's command tag
    sql, args = db.calls[0]
    assert sql == "DELETE FROM memories WHERE scope = $1"
    assert args == ("conv-a",)  # a single named scope, never a wildcard


async def test_delete_scope_without_matches_returns_zero() -> None:
    db = FakeDatabase(status="DELETE 0")
    assert await PgVectorMemoryStore(db).delete_scope("empty") == 0


async def test_delete_scope_wraps_a_backend_error() -> None:
    db = FakeDatabase(fail=asyncpg.PostgresError("boom"))
    with pytest.raises(MemoryStoreError, match="deleting memory scope 'conv-a'") as excinfo:
        await PgVectorMemoryStore(db).delete_scope("conv-a")
    assert isinstance(excinfo.value.__cause__, asyncpg.PostgresError)


async def test_delete_scope_wraps_a_malformed_status() -> None:
    db = FakeDatabase(status="DELETE not-a-count")
    with pytest.raises(MemoryStoreError, match="malformed delete status") as excinfo:
        await PgVectorMemoryStore(db).delete_scope("conv-a")
    assert isinstance(excinfo.value.__cause__, ValueError)


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
