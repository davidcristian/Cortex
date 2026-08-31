"""Isolation for the live pgvector contract run: a Postgres database of its own.

The ``integration``-marked suite here drives the real Postgres at ``CORTEX_MEMORY_DSN``, which on
a developer machine is the database the brain keeps its real memories in. Sharing the ``memories``
table with them made the run report on the table's contents rather than the adapter's behaviour:
``memory_contract.check_empty_search`` asserts ``search(k=5) == []`` over the whole table and
``check_ranks_by_similarity`` asserts an exact top-2, so one real memory fails a correct adapter.

So the live run opens a database of its own, ``LIVE_DB``, which the brain never opens: production
points ``CORTEX_MEMORY_DSN`` at ``cortex`` (docker/docker-compose.memory.yml). That is the same
cure the live Redis runs got, in the mechanism Postgres has for it: there is no ``SELECT n`` here,
so the database name in the DSN path takes the place of Redis's database index, and ``TRUNCATE``
of the one table takes the place of ``FLUSHDB``. A schema plus a ``search_path`` was the other
candidate and is rejected in the ADR-0002 addendum on the live-run database: the adapter's SQL is
unqualified (``FROM memories``), so a ``search_path`` that failed to apply would land every query,
including this module's ``TRUNCATE``, on the brain's own table, silently.

The bootstrap is per database, since pgvector is installed per database rather than per schema.
``docker/postgres/live-contract-db.sql`` applies it on a fresh data dir; on an older one the
database is missing, and this module fails the run with the two statements that create it rather
than falling back to the configured DSN, because a live run that quietly lands somewhere else is
worse than one that refuses to start.
"""

import os
from urllib.parse import urlsplit, urlunsplit

import asyncpg
import pytest

# The DSN the runbook hands the live run when the environment names none.
DEFAULT_DSN = "postgresql://cortex:cortex@127.0.0.1:5432/cortex"

# The database the live contract run owns and empties. Named for what it holds rather than for
# who owns it: at a psql prompt `cortex_live` beside `cortex` reads like the production one.
LIVE_DB = "cortex_contract"

# The URL schemes that carry the database name in the path component, which is what the rewrite
# below replaces. libpq accepts both spellings.
_PG_SCHEMES = frozenset({"postgresql", "postgres"})

_BOOTSTRAP = (
    f"the {LIVE_DB} database is missing or unbootstrapped; a data dir created before it existed"
    " never re-runs an initdb script, so create it once (docs/runbooks/memory-pgvector.md):\n"
    f"  docker compose ... exec postgres psql -U cortex -d cortex -c 'CREATE DATABASE {LIVE_DB};'\n"
    f"  docker compose ... exec postgres psql -U cortex -d {LIVE_DB}"
    " -f /docker-entrypoint-initdb.d/init.sql"
)


def live_dsn() -> str:
    """Return the configured DSN redirected onto ``LIVE_DB``.

    Refuses rather than guesses in the two cases where the rewrite would not be a redirect: a
    scheme that does not carry the database in its path, and a DSN that already names ``LIVE_DB``,
    which would mean the brain is pointed at the database this module truncates.
    """
    configured = os.environ.get("CORTEX_MEMORY_DSN", DEFAULT_DSN)
    parts = urlsplit(configured)
    if parts.scheme not in _PG_SCHEMES:
        pytest.fail(f"CORTEX_MEMORY_DSN {configured!r} names no postgresql:// database")
    if parts.path.strip("/") == LIVE_DB:
        pytest.fail(
            f"CORTEX_MEMORY_DSN {configured!r} names database {LIVE_DB}, which the live contract"
            " run reserves and empties; point the brain at another one"
        )
    return urlunsplit((parts.scheme, parts.netloc, f"/{LIVE_DB}", parts.query, parts.fragment))


async def connect() -> "asyncpg.Pool[asyncpg.Record]":
    """Open a pool on the live contract database, or fail the run legibly.

    Both ways it can be absent are answered here, before any check runs and before the adapter
    turns them into a ``MemoryStoreError`` that reads like an adapter bug: no such database, and a
    database created without the bootstrap, which leaves no ``memories`` table.
    """
    dsn = live_dsn()
    try:
        pool = await asyncpg.create_pool(dsn)
    except asyncpg.InvalidCatalogNameError:
        pytest.fail(_BOOTSTRAP)
    if await pool.fetchval("SELECT to_regclass('memories')") is None:
        await pool.close()
        pytest.fail(_BOOTSTRAP)
    return pool


async def reset(pool: "asyncpg.Pool[asyncpg.Record]") -> None:
    """Empty the live contract database, so the next check starts where the in-memory fake starts.

    Reads back the database the pool actually opened instead of trusting its caller: the truncate
    is safe only because it lands on ``LIVE_DB``, so that is checked where the damage would be and
    not merely where the DSN was built.
    """
    opened = await pool.fetchval("SELECT current_database()")
    if opened != LIVE_DB:
        pytest.fail(f"refusing to empty database {opened!r}; the live contract run owns {LIVE_DB}")
    await pool.execute("TRUNCATE TABLE memories")
