"""The same contract suite against real Redis, in the live runs' own database.

Integration-marked: excluded from CI and the coverage gate by the workspace addopts
(`-m "not integration"`); run manually on a host with Redis up, e.g.
`cd brain && uv run pytest -m integration --no-cov packages/session`. Here the `--no-cov`
matters, the 100% gate in addopts would otherwise fail the run. The store it drives is the
live-run database (see tests/live_redis.py), emptied before the suite and again after every
check, so each check starts from the empty store the fakeredis fixture also grants it and no
real session is ever read, written, or deleted.
"""

import contract
import live_redis
import pytest
from redis.asyncio import Redis

from cortex_session import RedisSessionStore


@pytest.mark.integration
async def test_redis_session_store_satisfies_the_contract_live() -> None:
    url = live_redis.live_redis_url()
    store = RedisSessionStore.from_url(url)
    cleanup = Redis.from_url(url)  # pyright: ignore[reportUnknownMemberType] - **kwargs untyped
    try:
        await live_redis.reset(cleanup)  # a killed prior run may have left records behind
        for check in contract.ALL_CHECKS:
            await check(store)
            # Per check, not once at the end: a check that FAILS still leaves an empty
            # database behind, so one bad run cannot poison every later one.
            await live_redis.reset(cleanup)
    finally:
        await live_redis.reset(cleanup)
        await cleanup.aclose()
        await store.aclose()
