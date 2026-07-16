"""The same contract suite against real Redis at CORTEX_REDIS_URL."""

import os
from typing import cast

import contract
import pytest
from redis.asyncio import Redis

from cortex_session import DEFAULT_REDIS_URL, RedisSessionStore

_PREFIX = "contract-"

_SESSIONS_KEY = "cortex:sessions"
# The pinned set (store.py's `_PINNED_KEY`): a missed contract pin would linger as a dangling
# pinned member across runs, and pinning forces its chat into every listing regardless of recency.
_PINNED_KEY = "cortex:sessions:pinned"


async def _sweep(cleanup: Redis) -> None:
    """Remove every contract-created message list, recency-index member, and pinned member."""
    pattern = f"cortex:session:{_PREFIX}*"
    keys = cast("list[bytes]", await cleanup.keys(pattern))  # pyright: ignore[reportUnknownMemberType]
    if keys:
        await cleanup.delete(*keys)
    members = cast(
        "list[bytes]",
        await cleanup.zrange(_SESSIONS_KEY, 0, -1),  # pyright: ignore[reportUnknownMemberType]
    )
    stale = [m for m in members if m.decode("utf-8").startswith(_PREFIX)]
    if stale:
        await cleanup.zrem(_SESSIONS_KEY, *stale)
    pinned = cast("set[bytes]", await cleanup.smembers(_PINNED_KEY))  # pyright: ignore[reportUnknownMemberType]
    stale_pins = [m for m in pinned if m.decode("utf-8").startswith(_PREFIX)]
    if stale_pins:
        await cleanup.srem(_PINNED_KEY, *stale_pins)


@pytest.mark.integration
async def test_redis_session_store_satisfies_the_contract_live() -> None:
    url = os.environ.get("CORTEX_REDIS_URL", DEFAULT_REDIS_URL)
    store = RedisSessionStore.from_url(url)
    cleanup = Redis.from_url(url)  # pyright: ignore[reportUnknownMemberType] - **kwargs untyped
    try:
        await _sweep(cleanup)  # a killed prior run may have left contract ids behind
        for check in contract.ALL_CHECKS:
            await check(store)
            # Per check, not once at the end: a check that FAILS still has its ids swept,
            # so one bad run cannot poison every later one.
            await _sweep(cleanup)
    finally:
        await _sweep(cleanup)
        await cleanup.aclose()
        await store.aclose()
