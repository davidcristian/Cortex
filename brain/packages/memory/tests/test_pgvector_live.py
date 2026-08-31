import live_postgres
import memory_contract
import pytest

from cortex_memory import PgVectorMemoryStore


@pytest.mark.integration
async def test_pgvector_store_satisfies_the_contract_live() -> None:
    admin = await live_postgres.connect()
    try:
        await live_postgres.reset(admin)
        for check in memory_contract.ALL_CHECKS:
            # A fresh store per check: one check closes the pool to make the backend unreachable.
            store = await PgVectorMemoryStore.connect(live_postgres.live_dsn())
            try:
                under_test = memory_contract.MemoryStoreUnderTest(
                    store=store, break_backend=store.aclose
                )
                await check(under_test)
            finally:
                await store.aclose()
            await live_postgres.reset(admin)
    finally:
        await live_postgres.reset(admin)
        await admin.close()
