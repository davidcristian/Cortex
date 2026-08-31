"""The ScheduleStore contract suite against real Redis, in the live runs' own database.

Integration-marked: excluded from CI and the coverage gate by the workspace addopts
(`-m "not integration"`); run manually on a host with Redis up, e.g.
`cd brain && uv run pytest -m integration --no-cov packages/session`. Here the `--no-cov`
matters, the 100% gate in addopts would otherwise fail the run. The store it drives is the
live-run database (see tests/live_redis.py), emptied before the suite and again after every
check. Its checks assert exact global views (``list_active``/``deliverable``) and claim
whatever is due, which is why this suite used to skip the moment the shared database held a
real schedule: a passing run that had asserted nothing. On a database of its own there is
nothing real to disturb and nothing to skip for (ADR-0025, ADR-0002).
"""

import live_redis
import pytest
import schedule_contract
from redis.asyncio import Redis

from cortex_session import RedisScheduleStore


@pytest.mark.integration
async def test_redis_schedule_store_satisfies_the_contract_live() -> None:
    url = live_redis.live_redis_url()
    store = RedisScheduleStore.from_url(url)
    cleanup = Redis.from_url(url)  # pyright: ignore[reportUnknownMemberType] - **kwargs untyped
    try:
        await live_redis.reset(cleanup)  # a killed prior run may have left records behind
        for check in schedule_contract.ALL_CHECKS:
            await check(store)
            await live_redis.reset(cleanup)  # each check assumes a fresh store, as the fixture does
    finally:
        await live_redis.reset(cleanup)
        await cleanup.aclose()
        await store.aclose()
