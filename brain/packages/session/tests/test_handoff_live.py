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
        await live_redis.reset(cleanup)
        for check in handoff_contract.ALL_CHECKS:
            await check(store)
            await live_redis.reset(cleanup)
    finally:
        await live_redis.reset(cleanup)
        await cleanup.aclose()
        await store.aclose()
