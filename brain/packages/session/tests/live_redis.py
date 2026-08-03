"""Isolation for the live-Redis contract runs: a logical database of their own."""

import os
from typing import cast
from urllib.parse import urlsplit, urlunsplit

import pytest
from redis.asyncio import Redis

from cortex_session import DEFAULT_REDIS_URL

# Redis serves 16 logical databases (0..15) out of the box and this repo's production
# configuration selects 0, so the live runs take the far end. Nothing they write is state the
# brain reads, and nothing they flush is state the brain owns.
LIVE_DB = 15

# The URL schemes that carry the database index in the path component, the rewrite below.
_TCP_SCHEMES = frozenset({"redis", "rediss"})


def live_redis_url() -> str:
    """Return the configured Redis URL redirected onto ``LIVE_DB``."""
    configured = os.environ.get("CORTEX_REDIS_URL", DEFAULT_REDIS_URL)
    parts = urlsplit(configured)
    if parts.scheme not in _TCP_SCHEMES:
        pytest.fail(f"CORTEX_REDIS_URL {configured!r} names no redis:// or rediss:// database")
    if parts.path.strip("/") == str(LIVE_DB):
        pytest.fail(
            f"CORTEX_REDIS_URL {configured!r} selects database {LIVE_DB}, which the live"
            " contract runs reserve and empty; point the brain at another one"
        )
    return urlunsplit((parts.scheme, parts.netloc, f"/{LIVE_DB}", parts.query, parts.fragment))


async def reset(client: Redis) -> None:
    """Empty the live database, so the next check starts where the fakeredis fixture starts."""
    # redis-py types both of these as partially Unknown (the pool's kwargs bag, and flushdb's
    # **kwargs); the cast pins what this file actually reads out of the first.
    opened = cast(
        "dict[str, object]",
        client.connection_pool.connection_kwargs,  # pyright: ignore[reportUnknownMemberType]
    ).get("db")
    if opened != LIVE_DB:
        pytest.fail(f"refusing to flush Redis database {opened!r}; the live runs own {LIVE_DB}")
    await client.flushdb()  # pyright: ignore[reportUnknownMemberType]
