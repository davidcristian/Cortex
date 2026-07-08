"""The same ScheduleStore contract suite against real Redis at CORTEX_REDIS_URL (ADR-0025).

Integration-marked: excluded from CI and the coverage gate by the workspace addopts
(`-m "not integration"`); run manually on a host with Redis up, e.g.
`cd brain && uv run pytest -m integration --no-cov packages/session`. Here the `--no-cov`
matters, the 100% gate in addopts would otherwise fail the run. Every check works on
ids prefixed `contract-`, and the sweep below removes those records and index members,
so the run leaves the store as it found it.
"""

import os
from typing import cast

import pytest
import schedule_contract
from redis.asyncio import Redis

from cortex_session import DEFAULT_REDIS_URL, RedisScheduleStore
from cortex_session.schedule_codec import DEAD_KEY, DELIVERABLE_KEY, DUE_KEY, FIRING_KEY

_PREFIX = "contract-"


async def _sweep(cleanup: Redis) -> None:
    """Remove every contract-created record, index member, and dead-letter field."""
    pattern = f"cortex:schedule:{_PREFIX}*"
    keys = cast("list[bytes]", await cleanup.keys(pattern))  # pyright: ignore[reportUnknownMemberType]
    if keys:
        await cleanup.delete(*keys)
    for index in (DUE_KEY, FIRING_KEY, DELIVERABLE_KEY):
        members = cast(
            "list[bytes]",
            await cleanup.zrange(index, 0, -1),  # pyright: ignore[reportUnknownMemberType]
        )
        stale = [m for m in members if m.decode("utf-8").startswith(_PREFIX)]
        if stale:
            await cleanup.zrem(index, *stale)
    fields = cast("list[bytes]", await cleanup.hkeys(DEAD_KEY))
    dead = [f for f in fields if f.decode("utf-8").startswith(_PREFIX)]
    if dead:
        await cleanup.hdel(DEAD_KEY, *dead)


@pytest.mark.integration
async def test_redis_schedule_store_satisfies_the_contract_live() -> None:
    url = os.environ.get("CORTEX_REDIS_URL", DEFAULT_REDIS_URL)
    store = RedisScheduleStore.from_url(url)
    cleanup = Redis.from_url(url)  # pyright: ignore[reportUnknownMemberType] - **kwargs untyped
    try:
        # The checks assert exact global views (list_active/deliverable) and claim whatever
        # is due, so a store holding REAL schedules must not be disturbed. Skip, don't risk.
        existing = cast(
            "list[bytes]",
            await cleanup.keys("cortex:schedule:*"),  # pyright: ignore[reportUnknownMemberType]
        )
        mine = f"cortex:schedule:{_PREFIX}"
        if any(not key.decode("utf-8").startswith(mine) for key in existing):
            pytest.skip("live schedule store holds real schedules; refusing to disturb them")
        for check in schedule_contract.ALL_CHECKS:
            await check(store)
            await _sweep(cleanup)  # each check assumes a fresh store, like the fixture grants
    finally:
        await _sweep(cleanup)
        await cleanup.aclose()
        await store.aclose()
