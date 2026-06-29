"""PgVectorMemoryStore: the MemoryStore port over Postgres + pgvector (ADR-0008).

One row per memory in ``memories(id, text, embedding vector, created_at)``. ``search`` ranks
by cosine distance (``<=>``) and returns cosine *similarity* as the score, so it is observably
interchangeable with ``InMemoryMemoryStore`` behind the port. This adapter only translates
between the core's values and SQL, with no business logic; every backend failure crosses the
port as ``MemoryStoreError`` with the cause chained.

The embedding is passed as a pgvector text literal and cast (``$n::vector``), and read back
via ``embedding::text``, so no driver-side vector-type registration is needed. Real pools are
built by ``connect``; the query surface is the injected ``Database`` port, which an asyncpg
pool satisfies (and a canned-row fake, the asyncpg analog of MockTransport, satisfies in CI).
"""

from collections.abc import Sequence
from typing import Any, Protocol, cast

import asyncpg

from cortex_core import MemoryRecord, MemoryStoreError, ScoredMemory

# asyncpg raises PostgresError for server-side failures, InterfaceError for client/pool
# misuse, and OSError for socket-level failures. All are wrapped as MemoryStoreError.
_WRAPPED = (asyncpg.PostgresError, asyncpg.InterfaceError, OSError)

_INSERT = "INSERT INTO memories (id, text, embedding, created_at) VALUES ($1, $2, $3::vector, $4)"
_SEARCH = (
    "SELECT id, text, embedding::text AS embedding, created_at,"
    " 1 - (embedding <=> $1::vector) AS score"
    " FROM memories ORDER BY embedding <=> $1::vector LIMIT $2"
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
    """Parse a pgvector text literal (``[0.1,0.2]``) back into a float tuple.

    A pgvector vector always has dimension >= 1, so the inner text is never empty; a
    malformed value raises ValueError, which ``search`` wraps as ``MemoryStoreError``.
    """
    inner = text.strip().strip("[]")
    return tuple(float(part) for part in inner.split(","))


def _to_scored(row: Row) -> ScoredMemory:
    """Map one result row to a ScoredMemory (raises to the caller's typed wrapper on bad shape)."""
    record = MemoryRecord(
        id=row["id"],
        text=row["text"],
        embedding=_from_literal(row["embedding"]),
        at=row["created_at"],
    )
    return ScoredMemory(record=record, score=float(row["score"]))


class PgVectorMemoryStore:
    """MemoryStore adapter over an asyncpg-compatible ``Database`` (ADR-0008)."""

    def __init__(self, db: Database) -> None:
        self._db = db

    @classmethod
    async def connect(cls, dsn: str) -> "PgVectorMemoryStore":
        """Build a store owning a fresh asyncpg pool for ``dsn``; close it via ``aclose()``."""
        pool = await asyncpg.create_pool(dsn)
        return cls(cast("Database", pool))

    async def aclose(self) -> None:
        """Release the pool's connections (call at composition-root shutdown)."""
        try:
            await self._db.close()
        except _WRAPPED as err:
            msg = "closing the memory store failed"
            raise MemoryStoreError(msg) from err

    async def add(self, record: MemoryRecord) -> None:
        """Persist one memory record."""
        try:
            await self._db.execute(
                _INSERT, record.id, record.text, _to_literal(record.embedding), record.at
            )
        except _WRAPPED as err:
            msg = f"adding memory {record.id!r} failed"
            raise MemoryStoreError(msg) from err

    async def search(self, embedding: Sequence[float], *, k: int) -> Sequence[ScoredMemory]:
        """Return the ``k`` records most similar to ``embedding``, most-similar first."""
        try:
            rows = await self._db.fetch(_SEARCH, _to_literal(embedding), k)
            return tuple(_to_scored(row) for row in rows)
        except _WRAPPED as err:
            msg = "memory search failed"
            raise MemoryStoreError(msg) from err
        except (KeyError, IndexError, TypeError, ValueError) as err:
            msg = "malformed memory row in search result"
            raise MemoryStoreError(msg) from err
