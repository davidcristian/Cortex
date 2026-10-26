"""PgVectorMemoryStore: the MemoryStore port over Postgres and pgvector."""

import asyncio
from collections.abc import Coroutine, Sequence
from typing import Any, Protocol, cast

import asyncpg

from cortex_core import (
    MemoryDataError,
    MemoryRecord,
    MemoryStoreError,
    PartialDeleteError,
    ScoredMemory,
)

# Server failures, client and pool misuse, and socket failures, in that order.
_WRAPPED = (asyncpg.PostgresError, asyncpg.InterfaceError, OSError)

# The share lock makes a concurrent tainted delete wait for this insert to commit, and a recalled
# row that delete already removed is not counted, so the record is not stored. Both statements lock
# in id order, so neither can hold a row the other waits on while it waits on one the other holds.
_INSERT = (
    "INSERT INTO memories (id, text, embedding, scope, tainted, created_at)"
    " SELECT $1, $2, $3::vector, $4, $5, $6"
    " WHERE (SELECT count(*) FROM (SELECT id FROM memories WHERE id = ANY($7::text[])"
    " ORDER BY id FOR SHARE) AS kept) = $8"
)
# $1 is the vector and $2 the limit in both search statements, so the scoped one can reuse the
# same leading arguments and append its scope list as $3.
_SELECT = (
    "SELECT id, text, embedding::text AS embedding, scope, tainted, created_at,"
    " 1 - (embedding <=> $1::vector) AS score FROM memories"
)
_SEARCH_ALL = f"{_SELECT} ORDER BY embedding <=> $1::vector LIMIT $2"
_SEARCH_SCOPED = f"{_SELECT} WHERE scope = ANY($3) ORDER BY embedding <=> $1::vector LIMIT $2"
_COUNT_ALL = "SELECT count(*) AS total FROM memories"
_COUNT_SCOPED = f"{_COUNT_ALL} WHERE scope = ANY($1)"
_COUNT_TAINTED = f"{_COUNT_ALL} WHERE tainted"
_COUNT_TAINTED_SCOPED = f"{_COUNT_TAINTED} AND scope = ANY($1)"
_DELETE_SCOPE = "DELETE FROM memories WHERE scope = $1"
_DELETE_TAINTED = (
    "DELETE FROM memories WHERE id IN"
    " (SELECT id FROM memories WHERE tainted ORDER BY id FOR UPDATE)"
)
_DELETE_TAINTED_SCOPED = (
    "DELETE FROM memories WHERE id IN"
    " (SELECT id FROM memories WHERE tainted AND scope = ANY($1) ORDER BY id FOR UPDATE)"
)


class Row(Protocol):
    """One result row keyed by column name; asyncpg ``Record`` and a plain dict both satisfy it."""

    def __getitem__(self, key: str, /) -> Any: ...  # noqa: ANN401 - a DB cell is genuinely dynamic


class Database(Protocol):
    """The slice of asyncpg the adapter uses; an asyncpg pool satisfies it, as does the CI fake."""

    async def execute(self, sql: str, /, *args: object) -> object: ...

    async def fetch(self, sql: str, /, *args: object) -> Sequence[Row]: ...

    async def close(self) -> None: ...


def _to_literal(embedding: Sequence[float]) -> str:
    """Render a vector as a pgvector text literal, e.g. ``[0.1,0.2,0.3]``."""
    return "[" + ",".join(repr(float(value)) for value in embedding) + "]"


def _from_literal(text: str) -> tuple[float, ...]:
    """Parse a pgvector text literal (``[0.1,0.2]``) back into a float tuple."""
    inner = text.strip().strip("[]")
    return tuple(float(part) for part in inner.split(","))


def _row_count(status: object) -> int:
    """Parse asyncpg's ``DELETE n`` or ``INSERT 0 n`` command tag into its row count."""
    return int(str(status).rsplit(" ", 1)[-1])


def _to_scored(row: Row) -> ScoredMemory:
    """Map one result row to a ScoredMemory (raises to the caller's typed wrapper on bad shape)."""
    record = MemoryRecord(
        id=row["id"],
        text=row["text"],
        embedding=_from_literal(row["embedding"]),
        at=row["created_at"],
        scope=row["scope"],
        tainted=row["tainted"],
    )
    return ScoredMemory(record=record, score=float(row["score"]))


class PgVectorMemoryStore:
    """MemoryStore adapter over an asyncpg-compatible ``Database``."""

    def __init__(self, db: Database, *, timeout_s: float | None = None) -> None:
        """Wrap ``db``; a statement that outlasts ``timeout_s`` fails as an unavailable store."""
        self._db = db
        self._timeout_s = timeout_s
        self._abandoned: set[asyncio.Task[Any]] = set()

    @classmethod
    async def connect(cls, dsn: str, *, timeout_s: float) -> "PgVectorMemoryStore":
        """Build a store owning a fresh asyncpg pool for ``dsn``; close it via ``aclose()``."""
        pool = await asyncpg.create_pool(dsn)
        return cls(cast("Database", pool), timeout_s=timeout_s)

    async def _bounded[T](self, statement: Coroutine[Any, Any, T]) -> T:
        """Await ``statement`` for at most the bound, raising ``TimeoutError`` past it."""
        if self._timeout_s is None:
            return await statement
        task = asyncio.ensure_future(statement)
        try:
            done, _ = await asyncio.wait({task}, timeout=self._timeout_s)
        except asyncio.CancelledError:
            self._abandon(task)
            raise
        if not done:
            self._abandon(task)
            raise TimeoutError
        return task.result()

    def _abandon(self, task: asyncio.Task[Any]) -> None:
        """Cancel ``task`` without waiting for it, keeping it referenced until it ends."""
        # asyncpg's pool release waits, shielded, for a cancel request the hung server never
        # answers, so awaiting the cancelled statement would hang exactly as long as the server.
        task.cancel()
        self._abandoned.add(task)
        task.add_done_callback(self._settle)

    def _settle(self, task: asyncio.Task[Any]) -> None:
        """Forget an abandoned statement that ended, reading its error so none goes unretrieved."""
        self._abandoned.discard(task)
        if not task.cancelled():
            task.exception()

    async def aclose(self) -> None:
        """Release the pool's connections (call at composition-root shutdown)."""
        try:
            await self._db.close()
        except _WRAPPED as err:
            msg = "closing the memory store failed"
            raise MemoryStoreError(msg) from err

    async def add(self, record: MemoryRecord, *, recalled: Sequence[str] = ()) -> bool:
        """Persist ``record`` only while every id in ``recalled`` is still stored."""
        kept = sorted(set(recalled))
        try:
            status = await self._bounded(
                self._db.execute(
                    _INSERT,
                    record.id,
                    record.text,
                    _to_literal(record.embedding),
                    record.scope,
                    record.tainted,
                    record.at,
                    kept,
                    len(kept),
                )
            )
            return _row_count(status) == 1
        except _WRAPPED as err:
            msg = f"adding memory {record.id!r} failed"
            raise MemoryStoreError(msg) from err
        except ValueError as err:
            msg = "malformed insert status from the memory store"
            raise MemoryDataError(msg) from err

    async def search(
        self, embedding: Sequence[float], *, k: int, scopes: Sequence[str] | None = None
    ) -> Sequence[ScoredMemory]:
        """Return the ``k`` records most similar to ``embedding``, most-similar first."""
        try:
            literal = _to_literal(embedding)
            if scopes is None:
                rows = await self._bounded(self._db.fetch(_SEARCH_ALL, literal, k))
            else:
                rows = await self._bounded(self._db.fetch(_SEARCH_SCOPED, literal, k, list(scopes)))
            return tuple(_to_scored(row) for row in rows)
        except _WRAPPED as err:
            msg = "memory search failed"
            raise MemoryStoreError(msg) from err
        except (KeyError, IndexError, TypeError, ValueError) as err:
            msg = "malformed memory row in search result"
            raise MemoryDataError(msg) from err

    async def count_candidates(self, *, scopes: Sequence[str] | None = None) -> int:
        """Return how many memories ``scopes`` holds, the width ``search`` ranked over."""
        return await self._count(_COUNT_ALL, _COUNT_SCOPED, scopes, "memory candidates")

    async def count_tainted(self, *, scopes: Sequence[str] | None = None) -> int:
        """Return how many tainted memories ``scopes`` holds (all scopes when None)."""
        return await self._count(_COUNT_TAINTED, _COUNT_TAINTED_SCOPED, scopes, "tainted memories")

    async def _count(
        self, every: str, scoped: str, scopes: Sequence[str] | None, counted: str
    ) -> int:
        """Run one count statement, ``scoped`` when ``scopes`` is given, else ``every``."""
        try:
            if scopes is None:
                rows = await self._bounded(self._db.fetch(every))
            else:
                rows = await self._bounded(self._db.fetch(scoped, list(scopes)))
            return int(rows[0]["total"])
        except _WRAPPED as err:
            msg = f"counting {counted} failed"
            raise MemoryStoreError(msg) from err
        except (KeyError, IndexError, TypeError, ValueError) as err:
            msg = "malformed count in the memory store's reply"
            raise MemoryDataError(msg) from err

    async def delete_scope(self, scope: str) -> int:
        """Hard-delete every memory in ``scope``; return how many rows were removed."""
        try:
            status = await self._bounded(self._db.execute(_DELETE_SCOPE, scope))
            return _row_count(status)
        except _WRAPPED as err:
            msg = f"deleting memory scope {scope!r} failed"
            raise MemoryStoreError(msg) from err
        except ValueError as err:
            msg = "malformed delete status from the memory store"
            raise MemoryDataError(msg) from err

    async def delete_tainted(self, *, scopes: Sequence[str] | None = None) -> int:
        """Hard-delete every tainted memory in ``scopes`` (all when None); return how many."""
        removed = 0
        try:
            while (count := await self._delete_tainted_once(scopes)) > 0:
                removed += count
        except MemoryStoreError as err:
            if removed == 0:
                raise
            msg = "deleting the tainted memories failed on a later pass"
            raise PartialDeleteError(msg, removed=removed) from err
        return removed

    async def _delete_tainted_once(self, scopes: Sequence[str] | None) -> int:
        """One tainted delete; a record committed while it waited on a share lock is left over."""
        try:
            if scopes is None:
                status = await self._bounded(self._db.execute(_DELETE_TAINTED))
            else:
                status = await self._bounded(self._db.execute(_DELETE_TAINTED_SCOPED, list(scopes)))
            return _row_count(status)
        except _WRAPPED as err:
            msg = "deleting the tainted memories failed"
            raise MemoryStoreError(msg) from err
        except ValueError as err:
            msg = "malformed delete status from the memory store"
            raise MemoryDataError(msg) from err
