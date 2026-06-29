"""The same contract suite against real Redis at CORTEX_REDIS_URL.

Integration-marked: excluded from CI and the coverage gate by the workspace addopts
(`-m "not integration"`); run manually on a host with Redis up, e.g.
`cd brain && uv run pytest -m integration --no-cov packages/session`. Here the `--no-cov`
matters, the 100% gate in addopts would otherwise fail the run.
"""

import os

import contract
import pytest
from redis.asyncio import Redis

from cortex_session import DEFAULT_REDIS_URL, RedisSessionStore


@pytest.mark.integration
async def test_redis_session_store_satisfies_the_contract_live() -> None:
    url = os.environ.get("CORTEX_REDIS_URL", DEFAULT_REDIS_URL)
    store = RedisSessionStore.from_url(url)
    used_session_ids: list[str] = []
    try:
        for check in contract.ALL_CHECKS:
            used_session_ids += await check(store)
    finally:
        cleanup = Redis.from_url(url)  # pyright: ignore[reportUnknownMemberType] - **kwargs untyped
        for session_id in used_session_ids:
            await cleanup.delete(f"cortex:session:{session_id}:messages")
        await cleanup.aclose()
        await store.aclose()
