"""The MemoryStore contract against real Postgres+pgvector at CORTEX_MEMORY_DSN.

Integration-marked: excluded from CI + the coverage gate (`-m "not integration"`); run on a
host with the DB up, e.g.
`cd brain && CORTEX_MEMORY_DSN=postgresql://cortex:cortex@127.0.0.1:5432/cortex \
  uv run pytest -m integration --no-cov packages/memory`. The `--no-cov` matters, the 100%
gate in the workspace addopts would otherwise fail the run. The `memories` table and the
`vector` extension must exist (docker/postgres/init.sql, applied by the compose).
"""

import os

import asyncpg
import memory_contract
import pytest

from cortex_memory import PgVectorMemoryStore

_DEFAULT_DSN = "postgresql://cortex:cortex@127.0.0.1:5432/cortex"
_CLEANUP = "DELETE FROM memories WHERE id LIKE 'contract-%'"


@pytest.mark.integration
async def test_pgvector_store_satisfies_the_contract_live() -> None:
    dsn = os.environ.get("CORTEX_MEMORY_DSN", _DEFAULT_DSN)
    store = await PgVectorMemoryStore.connect(dsn)
    admin = await asyncpg.create_pool(dsn)
    try:
        await admin.execute(_CLEANUP)  # start from a clean slate (survive a prior crash)
        for check in memory_contract.ALL_CHECKS:
            await check(store)
    finally:
        await admin.execute(_CLEANUP)
        await admin.close()
        await store.aclose()
