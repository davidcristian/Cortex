"""The same HandoffStore contract suite against real Redis at CORTEX_REDIS_URL.

Integration-marked: excluded from CI and the coverage gate by the workspace addopts
(`-m "not integration"`); run manually on a host with Redis up, e.g.
`cd brain && uv run pytest -m integration --no-cov packages/session`. Every check works on
ids prefixed `contract-`, and the sweep removes those records AND the active pointer when it
names one, so the run leaves the store as it found it. The suite skips outright if a REAL
(non-contract) handoff is active: its checks assert the global active slot, and a live swap
in flight must not be disturbed.
"""

import os
from typing import cast

import handoff_contract
import pytest
from redis.asyncio import Redis

from cortex_session import DEFAULT_REDIS_URL, RedisHandoffStore
from cortex_session.handoff_codec import ACTIVE_KEY

_PREFIX = "contract-"


async def _sweep(cleanup: Redis) -> None:
    """Remove every contract-created record and a contract-claimed active pointer."""
    pattern = f"cortex:handoff:{_PREFIX}*"
    keys = cast("list[bytes]", await cleanup.keys(pattern))  # pyright: ignore[reportUnknownMemberType]
    if keys:
        await cleanup.delete(*keys)
    pointer = await cleanup.get(ACTIVE_KEY)
    if pointer is not None and cast("bytes", pointer).decode("utf-8").startswith(_PREFIX):
        await cleanup.delete(ACTIVE_KEY)


@pytest.mark.integration
async def test_redis_handoff_store_satisfies_the_contract_live() -> None:
    url = os.environ.get("CORTEX_REDIS_URL", DEFAULT_REDIS_URL)
    store = RedisHandoffStore.from_url(url)
    cleanup = Redis.from_url(url)  # pyright: ignore[reportUnknownMemberType] - **kwargs untyped
    try:
        live = await store.active()
        if live is not None and not live.handoff_id.startswith(_PREFIX):
            pytest.skip("a real handoff is active; refusing to disturb it")
        await _sweep(cleanup)  # a killed prior run may have left contract ids behind
        for check in handoff_contract.ALL_CHECKS:
            await check(store)
            # Per check, not once at the end: a check that FAILS still has its ids swept,
            # so one bad run cannot poison every later one.
            await _sweep(cleanup)
    finally:
        await _sweep(cleanup)
        await cleanup.aclose()
        await store.aclose()
