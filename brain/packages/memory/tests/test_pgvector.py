import asyncio
import gc
from collections.abc import Awaitable, Callable, Mapping, Sequence
from datetime import UTC, datetime

import asyncpg
import pytest

from cortex_core import MemoryDataError, MemoryRecord, MemoryStoreError
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
    assert hits[0].record.scope == "work"
    assert (hits[0].record.tainted, hits[1].record.tainted) == (False, True)
    assert hits[0].score == 0.9
    sql, args = db.calls[0]
    assert "ORDER BY embedding <=>" in sql
    assert "tainted" in sql
    assert "WHERE scope" not in sql
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
    assert not isinstance(excinfo.value, MemoryDataError)


async def test_search_wraps_a_malformed_row_as_the_data_defect_it_is() -> None:
    rows: list[dict[str, object]] = [{"id": "a", "text": "alpha"}]
    with pytest.raises(MemoryDataError, match="malformed memory row") as excinfo:
        await PgVectorMemoryStore(FakeDatabase(rows=rows)).search((1.0,), k=1)
    assert isinstance(excinfo.value, MemoryStoreError)


async def test_count_candidates_asks_the_server_for_a_count_over_every_memory() -> None:
    db = FakeDatabase(rows=[{"total": 4213}])
    assert await PgVectorMemoryStore(db).count_candidates() == 4213
    sql, args = db.calls[0]
    assert sql == "SELECT count(*) AS total FROM memories"
    assert args == ()
    assert "LIMIT" not in sql


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
    assert not isinstance(excinfo.value, MemoryDataError)


@pytest.mark.parametrize(
    "rows", [[], [{"rows": 3}], [{"total": "not-a-number"}]], ids=["none", "unnamed", "unparsable"]
)
async def test_count_candidates_wraps_a_malformed_reply(rows: list[dict[str, object]]) -> None:
    with pytest.raises(MemoryDataError, match="malformed count") as excinfo:
        await PgVectorMemoryStore(FakeDatabase(rows=rows)).count_candidates()
    assert isinstance(excinfo.value.__cause__, KeyError | IndexError | ValueError)


async def test_delete_scope_executes_delete_and_returns_the_row_count() -> None:
    db = FakeDatabase(status="DELETE 3")
    removed = await PgVectorMemoryStore(db).delete_scope("conv-a")
    assert removed == 3
    sql, args = db.calls[0]
    assert sql == "DELETE FROM memories WHERE scope = $1"
    assert args == ("conv-a",)


async def test_delete_scope_without_matches_returns_zero() -> None:
    db = FakeDatabase(status="DELETE 0")
    assert await PgVectorMemoryStore(db).delete_scope("empty") == 0


async def test_delete_scope_wraps_a_backend_error() -> None:
    db = FakeDatabase(fail=asyncpg.PostgresError("boom"))
    with pytest.raises(MemoryStoreError, match="deleting memory scope 'conv-a'") as excinfo:
        await PgVectorMemoryStore(db).delete_scope("conv-a")
    assert isinstance(excinfo.value.__cause__, asyncpg.PostgresError)
    assert not isinstance(excinfo.value, MemoryDataError)


async def test_delete_scope_wraps_a_malformed_status() -> None:
    db = FakeDatabase(status="DELETE not-a-count")
    with pytest.raises(MemoryDataError, match="malformed delete status") as excinfo:
        await PgVectorMemoryStore(db).delete_scope("conv-a")
    assert isinstance(excinfo.value.__cause__, ValueError)


@pytest.mark.parametrize(
    ("scopes", "sql", "args"),
    [
        (None, "DELETE FROM memories WHERE tainted", ()),
        (("a", "b"), "DELETE FROM memories WHERE tainted AND scope = ANY($1)", (["a", "b"],)),
    ],
    ids=["every-scope", "scoped"],
)
async def test_delete_tainted_executes_its_delete_and_returns_the_row_count(
    scopes: Sequence[str] | None, sql: str, args: tuple[object, ...]
) -> None:
    db = FakeDatabase(status="DELETE 2")
    assert await PgVectorMemoryStore(db).delete_tainted(scopes=scopes) == 2
    assert db.calls == [(sql, args)]


async def test_delete_tainted_wraps_a_backend_error() -> None:
    db = FakeDatabase(fail=asyncpg.PostgresError("boom"))
    with pytest.raises(MemoryStoreError, match="deleting the tainted memories") as excinfo:
        await PgVectorMemoryStore(db).delete_tainted()
    assert isinstance(excinfo.value.__cause__, asyncpg.PostgresError)
    assert not isinstance(excinfo.value, MemoryDataError)


async def test_delete_tainted_wraps_a_malformed_status() -> None:
    db = FakeDatabase(status="DELETE not-a-count")
    with pytest.raises(MemoryDataError, match="malformed delete status") as excinfo:
        await PgVectorMemoryStore(db).delete_tainted(scopes=["a"])
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
    store = await PgVectorMemoryStore.connect("postgresql://cortex@localhost/cortex", timeout_s=5.0)
    await store.add(_record())
    assert seen == ["postgresql://cortex@localhost/cortex"]
    assert fake_pool.calls


class HangingDatabase:
    """A Database that never answers; cancelled, it waits for ``released`` like asyncpg's pool."""

    def __init__(self, *, fail_after_release: bool = False) -> None:
        self.released = asyncio.Event()
        self.cancelled = 0
        self._fail_after_release = fail_after_release

    async def _never(self) -> object:
        try:
            return await asyncio.get_running_loop().create_future()
        except asyncio.CancelledError:
            self.cancelled += 1
            await self.released.wait()
            if self._fail_after_release:
                raise ConnectionResetError from None
            raise

    async def execute(self, sql: str, /, *args: object) -> object:
        del sql, args
        return await self._never()

    async def fetch(self, sql: str, /, *args: object) -> Sequence[Mapping[str, object]]:
        del sql, args
        await self._never()
        return ()

    async def close(self) -> None:
        return None


def _operations(store: PgVectorMemoryStore) -> dict[str, Callable[[], Awaitable[object]]]:
    return {
        "add": lambda: store.add(_record()),
        "search": lambda: store.search((0.1, 0.2), k=1),
        "scoped search": lambda: store.search((0.1, 0.2), k=1, scopes=["s"]),
        "count": store.count_candidates,
        "scoped count": lambda: store.count_candidates(scopes=["s"]),
        "delete": lambda: store.delete_scope("s"),
        "delete tainted": store.delete_tainted,
    }


async def _ended(db: HangingDatabase, call: Awaitable[object]) -> asyncio.Future[object]:
    task = asyncio.ensure_future(call)
    done, _ = await asyncio.wait({task}, timeout=5)
    await asyncio.sleep(0)
    db.released.set()
    if not done:
        await asyncio.wait({task}, timeout=5)
        pytest.fail("the call outlived its bound")
    return task


@pytest.mark.parametrize(
    "operation",
    ["add", "search", "scoped search", "count", "scoped count", "delete", "delete tainted"],
)
async def test_a_hung_server_fails_as_unavailable_after_the_bound(operation: str) -> None:
    db = HangingDatabase()
    store = PgVectorMemoryStore(db, timeout_s=0.01)
    ended = await _ended(db, _operations(store)[operation]())
    with pytest.raises(MemoryStoreError) as caught:
        ended.result()
    assert not isinstance(caught.value, MemoryDataError)
    assert db.cancelled == 1


async def test_a_caller_cancelled_mid_statement_cancels_the_statement() -> None:
    db = HangingDatabase()
    store = PgVectorMemoryStore(db, timeout_s=5.0)
    call = asyncio.ensure_future(store.count_candidates())
    await asyncio.sleep(0.01)
    call.cancel()
    ended = await _ended(db, call)
    assert ended.cancelled()
    assert db.cancelled == 1


async def test_an_abandoned_statement_that_fails_later_leaves_no_unread_error() -> None:
    reported: list[dict[str, object]] = []
    loop = asyncio.get_running_loop()
    loop.set_exception_handler(lambda _loop, context: reported.append(context))
    try:
        db = HangingDatabase(fail_after_release=True)
        store = PgVectorMemoryStore(db, timeout_s=0.01)
        ended = await _ended(db, store.search((0.1,), k=1))
        failed = isinstance(ended.exception(), MemoryStoreError)
        # The error's traceback holds the abandoned statement, which must be collectable.
        del ended
        for _ in range(5):
            await asyncio.sleep(0)
        gc.collect()
    finally:
        loop.set_exception_handler(None)
    assert failed
    assert reported == []


async def test_connect_bounds_the_store_it_builds(monkeypatch: pytest.MonkeyPatch) -> None:
    db = HangingDatabase()

    async def hanging_pool(dsn: str) -> HangingDatabase:
        del dsn
        return db

    monkeypatch.setattr(asyncpg, "create_pool", hanging_pool)
    store = await PgVectorMemoryStore.connect(
        "postgresql://cortex@localhost/cortex", timeout_s=0.01
    )
    ended = await _ended(db, store.search((0.1,), k=1))
    with pytest.raises(MemoryStoreError, match="memory search failed"):
        ended.result()
