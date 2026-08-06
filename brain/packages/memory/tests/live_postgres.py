"""Isolation for the live pgvector contract run: a Postgres database of its own."""

import os
from urllib.parse import urlsplit, urlunsplit

import asyncpg
import pytest

DEFAULT_DSN = "postgresql://cortex:cortex@127.0.0.1:5432/cortex"

# The database the live run owns and empties. Deployments point CORTEX_MEMORY_DSN at `cortex`,
# so this one is never the brain's own.
LIVE_DB = "cortex_contract"

_PG_SCHEMES = frozenset({"postgresql", "postgres"})

_BOOTSTRAP = (
    f"the {LIVE_DB} database is missing or unbootstrapped; a data dir created before it existed"
    " never re-runs an initdb script, so create it once (docs/runbooks/memory-pgvector.md):\n"
    f"  docker compose ... exec postgres psql -U cortex -d cortex -c 'CREATE DATABASE {LIVE_DB};'\n"
    f"  docker compose ... exec postgres psql -U cortex -d {LIVE_DB}"
    " -f /docker-entrypoint-initdb.d/init.sql"
)


def live_dsn() -> str:
    """Return the configured DSN redirected onto ``LIVE_DB``."""
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
    """Open a pool on the live contract database, or fail the run legibly."""
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
    """Empty the live contract database, so the next check starts where the fake starts."""
    opened = await pool.fetchval("SELECT current_database()")
    if opened != LIVE_DB:
        pytest.fail(f"refusing to empty database {opened!r}; the live contract run owns {LIVE_DB}")
    await pool.execute("TRUNCATE TABLE memories")
