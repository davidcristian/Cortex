"""The MemoryStore contract against real Postgres+pgvector at CORTEX_MEMORY_DSN."""

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
