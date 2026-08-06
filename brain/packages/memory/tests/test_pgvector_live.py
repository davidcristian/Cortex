"""The MemoryStore contract against real Postgres+pgvector, in the live run's own database."""

import live_postgres
import memory_contract
import pytest

from cortex_memory import PgVectorMemoryStore


@pytest.mark.integration
async def test_pgvector_store_satisfies_the_contract_live() -> None:
    admin = await live_postgres.connect()  # first, so a missing bootstrap fails legibly
    store = await PgVectorMemoryStore.connect(live_postgres.live_dsn())
    try:
        await live_postgres.reset(admin)  # a killed prior run may have left rows behind
        for check in memory_contract.ALL_CHECKS:
            await check(store)
            # Per check, not once at the end: a check that FAILS still leaves an empty
            # table behind, so one bad run cannot poison every later one.
            await live_postgres.reset(admin)
    finally:
        await live_postgres.reset(admin)
        await admin.close()
        await store.aclose()
