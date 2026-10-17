import asyncio
from datetime import UTC, datetime
from typing import cast

import asyncpg
import live_postgres
import memory_contract
import pytest

from cortex_core import MemoryRecord
from cortex_memory import Database, PgVectorMemoryStore

_AT = datetime(2026, 10, 17, 6, 0, 0, tzinfo=UTC)


@pytest.mark.integration
async def test_pgvector_store_satisfies_the_contract_live() -> None:
    admin = await live_postgres.connect()
    try:
        await live_postgres.reset(admin)
        for check in memory_contract.ALL_CHECKS:
            # A fresh store per check: one check closes the pool to make the backend unreachable.
            store = await PgVectorMemoryStore.connect(live_postgres.live_dsn(), timeout_s=10.0)
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


def _tainted(record_id: str) -> MemoryRecord:
    return MemoryRecord(
        id=record_id, text=record_id, embedding=(1.0, 0.0), at=_AT, scope="global", tainted=True
    )


async def _race_setup() -> tuple["asyncpg.Pool[asyncpg.Record]", PgVectorMemoryStore]:
    admin = await live_postgres.connect()
    await live_postgres.reset(admin)
    pooled = await PgVectorMemoryStore.connect(live_postgres.live_dsn(), timeout_s=10.0)
    await pooled.add(_tainted("recalled"))
    return admin, pooled


@pytest.mark.integration
async def test_a_forget_waiting_on_a_record_removes_it_on_its_next_pass_live() -> None:
    admin, forgetter = await _race_setup()
    holder = await asyncpg.connect(live_postgres.live_dsn())
    try:
        transaction = holder.transaction()
        await transaction.start()
        recorder = PgVectorMemoryStore(cast("Database", holder))
        assert await recorder.add(_tainted("answer"), recalled=["recalled"]) is True
        forget = asyncio.ensure_future(forgetter.delete_tainted())
        await asyncio.sleep(0.5)
        assert not forget.done()
        await transaction.commit()
        assert await forget == 2
        assert await admin.fetchval("SELECT count(*) FROM memories") == 0
    finally:
        await holder.close()
        await forgetter.aclose()
        await live_postgres.reset(admin)
        await admin.close()


@pytest.mark.integration
async def test_a_record_waiting_on_a_forget_stores_nothing_live() -> None:
    admin, recorder = await _race_setup()
    holder = await asyncpg.connect(live_postgres.live_dsn())
    try:
        transaction = holder.transaction()
        await transaction.start()
        assert await PgVectorMemoryStore(cast("Database", holder)).delete_tainted() == 1
        record = asyncio.ensure_future(recorder.add(_tainted("answer"), recalled=["recalled"]))
        await asyncio.sleep(0.5)
        assert not record.done()
        await transaction.commit()
        assert await record is False
        assert await admin.fetchval("SELECT count(*) FROM memories") == 0
    finally:
        await holder.close()
        await recorder.aclose()
        await live_postgres.reset(admin)
        await admin.close()
