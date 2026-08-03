"""The same HandoffStore contract suite against real Redis, in the live runs' own database."""

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
            # Per check, not once at the end: a check that FAILS still leaves an empty
            # database behind, so one bad run cannot poison every later one.
            await live_redis.reset(cleanup)
    finally:
        await live_redis.reset(cleanup)
        await cleanup.aclose()
        await store.aclose()
