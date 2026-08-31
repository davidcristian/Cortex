"""The same HandoffStore contract suite against real Redis, in the live runs' own database.

Integration-marked: excluded from CI and the coverage gate by the workspace addopts
(`-m "not integration"`); run manually on a host with Redis up, e.g.
`cd brain && uv run pytest -m integration --no-cov packages/session`. The store it drives is
the live-run database (see tests/live_redis.py), emptied before the suite and again after
every check. That database holds no real handoff, so the checks may assert the global active
slot outright; this suite used to skip whenever a real handoff was in flight, which spared the
swap but passed while asserting nothing.
"""

import handoff_contract
import live_redis
import pytest
from redis.asyncio import Redis

from cortex_session import RedisHandoffStore


@pytest.mark.integration
async def test_redis_handoff_store_satisfies_the_contract_live() -> None:
    url = live_redis.live_redis_url()
    store = RedisHandoffStore.from_url(url)
    cleanup = Redis.from_url(url)  # pyright: ignore[reportUnknownMemberType] - **kwargs untyped
    try:
        await live_redis.reset(cleanup)  # a killed prior run may have left records behind
        for check in handoff_contract.ALL_CHECKS:
            await check(store)
            # Per check, not once at the end: a check that FAILS still leaves an empty database
            # behind, so a failure cannot leave records behind for the checks that follow.
            await live_redis.reset(cleanup)
    finally:
        await live_redis.reset(cleanup)
        await cleanup.aclose()
        await store.aclose()
