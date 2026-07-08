"""The RedisScheduleStore's claim path + the WATCH-fenced transition helpers (ADR-0025).

Split from ``schedules.py`` by responsibility (the 300-line cap) when the post-review
hardening made every guarded transition **optimistically atomic**: the token/status guard
and the state write now share one WATCH→MULTI/EXEC transaction, so a ``cancel``/``ack``
racing a fire can no longer land between a guard read and its write and be silently
overwritten. A concurrent touch of the record key makes ``EXEC`` raise ``WatchError``,
which every caller treats as "the other transition won" (``False``/skip, the same answer
as a stale fencing token). Module functions over the injected client; ``schedules.py``
delegates and owns the ``RedisError``→``ScheduleStoreError`` wrapping at the port edge.
"""

import logging
from contextlib import suppress
from dataclasses import replace
from datetime import datetime, timedelta
from typing import cast
from uuid import uuid4

from redis.asyncio import Redis
from redis.asyncio.client import Pipeline
from redis.exceptions import WatchError

from cortex_core import ScheduleClaim, ScheduledItem, ScheduleStatus, ScheduleStoreError
from cortex_session.schedule_codec import (
    DEAD_KEY,
    DELIVERABLE_KEY,
    DUE_KEY,
    FIRING_KEY,
    decode,
    encode,
    record_key,
)

logger = logging.getLogger(__name__)

WatchedState = tuple[ScheduledItem, str | None, datetime | None]


async def ids(client: Redis, key: str, *, upto: float | None = None, limit: int = 8) -> list[str]:
    """Members of one index ZSET, score order; score-bounded and counted when ``upto``."""
    if upto is None:
        # zrange's return type is partially Any in redis-py's typing (withscores overloads).
        raw = await client.zrange(key, 0, -1)  # pyright: ignore[reportUnknownMemberType]
    else:
        # zrangebyscore's return type is partially Any in redis-py's typing (overloads).
        raw = await client.zrangebyscore(  # pyright: ignore[reportUnknownMemberType]
            key, "-inf", upto, start=0, num=limit
        )
    return [member.decode("utf-8") for member in cast("list[bytes]", raw)]


async def watched_state(pipe: Pipeline, item_id: str) -> WatchedState | None:
    """WATCH the record key, then read it (the guard half of a fenced transition).

    ``None`` when the record is gone (cancelled/expired); a corrupt record raises
    ``ScheduleStoreError`` for the caller to translate. Leaving the ``async with`` block
    resets the pipeline, clearing the watch on every early return.
    """
    await pipe.watch(record_key(item_id))
    raw = await pipe.get(record_key(item_id))
    if raw is None:
        return None
    return decode(raw, item_id)


async def release_claim(client: Redis, claim: ScheduleClaim) -> bool:
    """Un-claim (FIRING → PENDING, due unchanged) under the token; stale/raced no-ops False."""
    async with client.pipeline(transaction=True) as pipe:
        state = await watched_state(pipe, claim.item.id)
        if state is None:
            return False
        item, live_token, _ = state
        if item.status is not ScheduleStatus.FIRING or live_token != claim.token:
            return False
        pending = replace(item, status=ScheduleStatus.PENDING)
        pipe.multi()
        pipe.set(record_key(item.id), encode(pending, claim=None, claimed_at=None))
        pipe.zrem(FIRING_KEY, item.id)
        pipe.zadd(DUE_KEY, {item.id: item.due_at.timestamp()})
        try:
            await pipe.execute()
        except WatchError:
            return False
    return True


async def quarantine(client: Redis, item_id: str, raw: bytes | str) -> None:
    """Dead-letter an undecodable claimed record so the pass degrades by one item."""
    logger.error("quarantining corrupt schedule record %r to %r", item_id, DEAD_KEY)
    async with client.pipeline(transaction=True) as pipe:
        pipe.hset(DEAD_KEY, item_id, raw)
        pipe.zrem(DUE_KEY, item_id)
        pipe.zrem(FIRING_KEY, item_id)
        pipe.zrem(DELIVERABLE_KEY, item_id)
        pipe.delete(record_key(item_id))
        await pipe.execute()


async def _claim_one(client: Redis, item_id: str, now: datetime) -> ScheduleClaim | None:
    """Move one eligible item to FIRING under a fresh token, the guard WATCH-fenced.

    A record raced away (cancelled) or claimed by a concurrent transition skips (None);
    an undecodable one quarantines; a dangling index entry is dropped.
    """
    async with client.pipeline(transaction=True) as pipe:
        await pipe.watch(record_key(item_id))
        raw = await pipe.get(record_key(item_id))
        if raw is None:
            # A dangling index entry (e.g. a crash between EXECs long past); drop it.
            pipe.multi()
            pipe.zrem(DUE_KEY, item_id)
            pipe.zrem(FIRING_KEY, item_id)
            with suppress(WatchError):
                await pipe.execute()
            return None
        try:
            item, _, _ = decode(raw, item_id)
        except ScheduleStoreError:
            logger.exception("undecodable schedule record on the claim path")
            await pipe.unwatch()
            await quarantine(client, item_id, raw)
            return None
        firing = replace(item, status=ScheduleStatus.FIRING)
        token = str(uuid4())
        pipe.multi()
        pipe.set(record_key(item_id), encode(firing, claim=token, claimed_at=now))
        pipe.zrem(DUE_KEY, item_id)
        pipe.zadd(FIRING_KEY, {item_id: now.timestamp()})
        try:
            await pipe.execute()
        except WatchError:
            return None
    return ScheduleClaim(item=firing, token=token)


async def claim_due(
    client: Redis, now: datetime, *, lease: timedelta, limit: int
) -> tuple[ScheduleClaim, ...]:
    """Claim due PENDING items and lease-expired FIRING ones, oldest-due-first.

    Candidates come capped from both indexes, so up to ``2 * limit`` are claimed and the
    overflow past ``limit`` (by due order) is released again. This is a bounded surplus at
    personal scale, and simpler than ranking across two differently-scored ZSETs.
    """
    due = await ids(client, DUE_KEY, upto=now.timestamp(), limit=limit)
    expired = await ids(client, FIRING_KEY, upto=(now - lease).timestamp(), limit=limit)
    claims: list[ScheduleClaim] = []
    for item_id in dict.fromkeys(due + expired):
        claim = await _claim_one(client, item_id, now)
        if claim is not None:
            claims.append(claim)
    claims.sort(key=lambda claim: claim.item.due_at)
    for surplus in claims[limit:]:
        await release_claim(client, surplus)
    return tuple(claims[:limit])
