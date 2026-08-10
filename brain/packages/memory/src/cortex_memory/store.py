"""PgVectorMemoryStore: the MemoryStore port over Postgres + pgvector (ADR-0008).

One row per memory in ``memories(id, text, embedding vector, scope, tainted, created_at)``.
``search`` ranks by cosine distance (``<=>``) and returns cosine *similarity* as the score, so it
is observably interchangeable with ``InMemoryMemoryStore`` behind the port; a non-``None``
``scopes`` filters candidates to those namespaces first (``WHERE scope = ANY``, ADR-0008 scoping
addendum). ``tainted``, the untrusted-provenance marker (ADR-0019), is stored and read back so a
tainted memory is fenced on recall. This adapter only translates between the core's values and
SQL, never business logic; every backend failure crosses the port as ``MemoryStoreError`` with the
cause chained.

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

_INSERT = (
    "INSERT INTO memories (id, text, embedding, scope, tainted, created_at)"
    " VALUES ($1, $2, $3::vector, $4, $5, $6)"
)
# The SELECT list is shared; the scoped variant only adds a WHERE that filters candidates to the
# requested namespaces before ranking (ADR-0008 scoping addendum). $1/$2 stay the vector/limit in
# both, so the args tuple's head is identical and only the optional scope list ($3) is appended.
_SELECT = (
    "SELECT id, text, embedding::text AS embedding, scope, tainted, created_at,"
    " 1 - (embedding <=> $1::vector) AS score FROM memories"
)
_SEARCH_ALL = f"{_SELECT} ORDER BY embedding <=> $1::vector LIMIT $2"
_SEARCH_SCOPED = f"{_SELECT} WHERE scope = ANY($3) ORDER BY embedding <=> $1::vector LIMIT $2"
# How wide the candidate set was, which the ranked SELECT above cannot say (ADR-0038
# candidate-count addendum). Deliberately a second statement rather than a ``count(*) OVER ()``
# on the ranked one: the window function must buffer every candidate row, embeddings included,
# before the LIMIT can apply, which measured 2.85x the plain search at 100k rows, while this
# costs a fraction of it because ``memories_scope_idx`` serves it as an index-only scan that
# never touches the vectors. Exact rather than capped for the same reason: there is nothing
# left to save. The two statements are not one transaction, which the audit value documents.
_COUNT_ALL = "SELECT count(*) AS total FROM memories"
_COUNT_SCOPED = f"{_COUNT_ALL} WHERE scope = ANY($1)"
# The forget primitive (ADR-0008 delete-scope addendum): drop one whole namespace. The
# ``memories_scope_idx`` btree serves the equality, so no schema change is owed.
_DELETE_SCOPE = "DELETE FROM memories WHERE scope = $1"


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


def _deleted_count(status: object) -> int:
    """Parse asyncpg's ``DELETE n`` command tag into the number of rows removed.

    asyncpg returns the command status string for a write, and the row count is its final field.
    A tag that does not end in an integer is a broken backend contract and raises ``ValueError``,
    which ``delete_scope`` wraps as ``MemoryStoreError`` (the malformed-response path ``search``
    already guards for a row).
    """
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
                _INSERT,
                record.id,
                record.text,
                _to_literal(record.embedding),
                record.scope,
                record.tainted,
                record.at,
            )
        except _WRAPPED as err:
            msg = f"adding memory {record.id!r} failed"
            raise MemoryStoreError(msg) from err

    async def search(
        self, embedding: Sequence[float], *, k: int, scopes: Sequence[str] | None = None
    ) -> Sequence[ScoredMemory]:
        """Return the ``k`` records most similar to ``embedding``, most-similar first.

        ``scopes`` (ADR-0008 addendum) filters candidates to those namespaces via
        ``WHERE scope = ANY``; ``None`` ranks over every memory (the global-space default).
        """
        try:
            literal = _to_literal(embedding)
            if scopes is None:
                rows = await self._db.fetch(_SEARCH_ALL, literal, k)
            else:
                rows = await self._db.fetch(_SEARCH_SCOPED, literal, k, list(scopes))
            return tuple(_to_scored(row) for row in rows)
        except _WRAPPED as err:
            msg = "memory search failed"
            raise MemoryStoreError(msg) from err
        except (KeyError, IndexError, TypeError, ValueError) as err:
            msg = "malformed memory row in search result"
            raise MemoryStoreError(msg) from err

    async def count_candidates(self, *, scopes: Sequence[str] | None = None) -> int:
        """Return how many memories ``scopes`` holds, the width ``search`` ranked over.

        ``scopes`` filters exactly as it does for ``search`` (``WHERE scope = ANY``), so the two
        describe one candidate set; ``None`` counts every memory. This is the server's own
        ``count(*)`` and never ``len`` of anything this adapter fetched, which is the distinction
        the verb exists for (ADR-0038 candidate-count addendum).
        """
        try:
            if scopes is None:
                rows = await self._db.fetch(_COUNT_ALL)
            else:
                rows = await self._db.fetch(_COUNT_SCOPED, list(scopes))
            return int(rows[0]["total"])
        except _WRAPPED as err:
            msg = "counting memory candidates failed"
            raise MemoryStoreError(msg) from err
        except (KeyError, IndexError, TypeError, ValueError) as err:
            msg = "malformed count in the memory store's reply"
            raise MemoryStoreError(msg) from err

    async def delete_scope(self, scope: str) -> int:
        """Hard-delete every memory in ``scope``; return how many rows were removed.

        ``DELETE FROM memories WHERE scope = $1`` (ADR-0008 delete-scope addendum), no schema
        change: a scope with no rows removes nothing and returns 0. A hard delete is right here,
        unlike a session tombstone, because ``search`` is a stateless top-k scan with no in-flight
        read of a specific id to fail cleanly, so a removed row leaves the candidate pool.
        """
        try:
            status = await self._db.execute(_DELETE_SCOPE, scope)
            return _deleted_count(status)
        except _WRAPPED as err:
            msg = f"deleting memory scope {scope!r} failed"
            raise MemoryStoreError(msg) from err
        except ValueError as err:
            msg = "malformed delete status from the memory store"
            raise MemoryStoreError(msg) from err
