"""The MemoryStore contract against real Postgres+pgvector, in the live run's own database.

Integration-marked: excluded from CI + the coverage gate (`-m "not integration"`); run on a
host with the DB up, e.g.
`cd brain && CORTEX_MEMORY_DSN=postgresql://cortex:cortex@127.0.0.1:5432/cortex \
  uv run pytest -m integration --no-cov packages/memory`. The `--no-cov` matters, the 100%
gate in the workspace addopts would otherwise fail the run. The store it drives is the
`cortex_contract` database (see tests/live_postgres.py), emptied before the suite and again after
every check, so each check starts from the empty store the in-memory fake also grants it and no
real memory is ever read, written, or deleted. That database and its `vector` extension and
`memories` table are bootstrapped by docker/postgres/live-contract-db.sql through the compose.
"""

import live_postgres
import memory_contract
import pytest

from cortex_memory import PgVectorMemoryStore


@pytest.mark.integration
async def test_pgvector_store_satisfies_the_contract_live() -> None:
    admin = await live_postgres.connect()  # first, so a missing bootstrap fails legibly
    try:
        await live_postgres.reset(admin)  # a killed prior run may have left rows behind
        for check in memory_contract.ALL_CHECKS:
            # A store per check, because one check ends by taking its backend away: the knob is
            # `aclose`, which really closes the pool this adapter owns, so asyncpg raises its own
            # `InterfaceError('pool is closed')` from inside every verb and the adapter's own
            # wrapping is what the check reads. Nothing here stands in for that translation.
            store = await PgVectorMemoryStore.connect(live_postgres.live_dsn())
            try:
                under_test = memory_contract.MemoryStoreUnderTest(
                    store=store, break_backend=store.aclose
                )
                await check(under_test)
            finally:
                await store.aclose()  # idempotent, so the broken arm closes exactly once
            # Per check, not once at the end: a check that FAILS still leaves an empty
            # table behind, so one bad run cannot poison every later one.
            await live_postgres.reset(admin)
    finally:
        await live_postgres.reset(admin)
        await admin.close()
