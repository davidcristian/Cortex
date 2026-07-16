"""The same contract suite against real Redis at CORTEX_REDIS_URL.

Integration-marked: excluded from CI and the coverage gate by the workspace addopts
(`-m "not integration"`); run manually on a host with Redis up, e.g.
`cd brain && uv run pytest -m integration --no-cov packages/session`. Here the `--no-cov`
matters, the 100% gate in addopts would otherwise fail the run. Every check works on ids
prefixed `contract-`, and the sweep below removes those message lists AND their recency-index
members, so the run leaves the store as it found it.
"""

import os
from typing import cast

import contract
import pytest
from redis.asyncio import Redis

from cortex_session import DEFAULT_REDIS_URL, RedisSessionStore

_PREFIX = "contract-"

# The recency index `list_sessions` reads (store.py's private `_SESSIONS_KEY`), restated
# here because a sweep that misses it leaves dangling members: they outlive the message
# lists, accumulate across runs, and eventually push a check's own sessions out of the
# `limit=50` window it asserts over.
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
