"""Isolation for the live-Redis contract runs: a logical database of their own.

Every ``integration``-marked suite in this directory drives the real Redis at
``CORTEX_REDIS_URL``, which on a developer machine is the same instance the brain keeps its
real state in. Sharing a keyspace with that state produced wrong results in both directions.
``contract.check_a_pinned_chat_escapes_the_recency_window`` reads ``list_sessions(limit=3)``,
so its three fixture chats have to BE the recency window; real chats more recent than their
fixed dates filled it instead, and the check failed over an adapter that was correct. The
schedule and handoff runs handled the same hazard by skipping outright whenever real records
were present, which passed while asserting nothing.

So the live runs select their own database index, ``LIVE_DB``, which the brain never opens:
production selects database 0 everywhere (``DEFAULT_REDIS_URL`` and the ``CORTEX_REDIS_URL``
that docker/docker-compose.yml sets). That gives every check the same precondition the
fakeredis fixture already grants it, an empty store, so the fake and the real adapter run the
identical suite rather than one suite and a hedged version of it. The argument, and the
designs it beat, are in the ADR-0002 addendum on the live-run database.
"""

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

# The URL schemes that carry the database index in the path component, which is what the rewrite
# below replaces.
_TCP_SCHEMES = frozenset({"redis", "rediss"})


def live_redis_url() -> str:
    """Return the configured Redis URL redirected onto ``LIVE_DB``.

    Fails the run in the two cases where the rewrite would not be a redirect: a scheme that does
    not carry the database in its path (``unix://`` puts the socket there), and a URL that
    already selects ``LIVE_DB``, which would mean production is pointed at the database ``reset``
    flushes.
    """
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
    """Empty the live database, so the next check starts where the fakeredis fixture starts.

    The database the client actually opened is read back rather than taken from the caller: the
    flush is safe only because it lands on ``LIVE_DB``, so that is checked where the flush
    happens and not only where the URL was built. Flushing the whole database is what lets the
    suites stop restating the adapters' key layouts, a coupling that goes stale whenever an
    adapter grows a key.
    """
    # redis-py types both of these as partially Unknown (the pool's kwargs bag, and flushdb's
    # **kwargs); the cast pins what this file actually reads out of the first.
    opened = cast(
        "dict[str, object]",
        client.connection_pool.connection_kwargs,  # pyright: ignore[reportUnknownMemberType]
    ).get("db")
    if opened != LIVE_DB:
        pytest.fail(f"refusing to flush Redis database {opened!r}; the live runs own {LIVE_DB}")
    await client.flushdb()  # pyright: ignore[reportUnknownMemberType]
