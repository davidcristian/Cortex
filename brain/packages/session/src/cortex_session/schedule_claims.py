"""The RedisScheduleStore's claim path and the WATCH-fenced transition helpers."""

import logging
from collections.abc import Callable
from contextlib import suppress
from dataclasses import replace
from datetime import datetime, timedelta
from typing import cast
from uuid import uuid4

from redis.asyncio import Redis
from redis.asyncio.client import Pipeline
from redis.exceptions import WatchError

from cortex_core import (
    ScheduleClaim,
    ScheduledItem,
    ScheduleEdit,
    ScheduleStatus,
    ScheduleStoreError,
    apply_edit,
)
from cortex_session.schedule_codec import (
    DEAD_KEY,
    DELIVERABLE_KEY,
    DUE_KEY,
    FIRING_KEY,
    DeadLetter,
    decode,
    encode,
    record_key,
)

logger = logging.getLogger(__name__)

WatchedState = tuple[ScheduledItem, str | None, datetime | None]
Plan = Callable[[Pipeline, WatchedState], bool]


async def ids(client: Redis, key: str, *, upto: float | None = None, limit: int = 8) -> list[str]:
    """Members of one index ZSET in score order, bounded by ``upto`` and capped at ``limit``."""
    if upto is None:
        raw = await client.zrange(key, 0, -1)  # pyright: ignore[reportUnknownMemberType]
    else:
        raw = await client.zrangebyscore(  # pyright: ignore[reportUnknownMemberType]
            key, "-inf", upto, start=0, num=limit
        )
    return [member.decode("utf-8") for member in cast("list[bytes]", raw)]


async def watched_state(pipe: Pipeline, item_id: str) -> WatchedState | None:
    """WATCH the record key, then read it (the guard half of a fenced transition)."""
    await pipe.watch(record_key(item_id))
    raw = await pipe.get(record_key(item_id))
    if raw is None:
        return None
    return decode(raw, item_id)


async def fenced(client: Redis, item_id: str, plan: Plan) -> bool:
    """Commit what ``plan`` queues after ``multi`` on the watched record; a raced write reads again.

    A missing record, or a ``plan`` answering False, returns False without a write.
    """
    while True:
        async with client.pipeline(transaction=True) as pipe:
            state = await watched_state(pipe, item_id)
            if state is None or not plan(pipe, state):
                return False
            try:
                await pipe.execute()
            except WatchError:
                continue
        return True


def holds(state: WatchedState, claim: ScheduleClaim) -> bool:
    """Whether the read record is still FIRING under ``claim``'s token."""
    item, live_token, _ = state
    return item.status is ScheduleStatus.FIRING and live_token == claim.token


async def release_claim(client: Redis, claim: ScheduleClaim) -> bool:
    """Un-claim under the token (FIRING to PENDING, due unchanged); False when it is stale."""

    def plan(pipe: Pipeline, state: WatchedState) -> bool:
        if not holds(state, claim):
            return False
        pending = replace(state[0], status=ScheduleStatus.PENDING)
        pipe.multi()
        pipe.set(record_key(pending.id), encode(pending, claim=None, claimed_at=None))
        pipe.zrem(FIRING_KEY, pending.id)
        pipe.zadd(DUE_KEY, {pending.id: pending.due_at.timestamp()})
        return True

    return await fenced(client, claim.item.id, plan)


async def edit_item(client: Redis, item_id: str, edit: ScheduleEdit) -> bool:
    """Change a non-FIRING item's text or recurrence under a WATCH fence; False otherwise."""

    def plan(pipe: Pipeline, state: WatchedState) -> bool:
        if state[0].status is ScheduleStatus.FIRING:
            return False
        updated = apply_edit(state[0], edit)
        pipe.multi()
        pipe.set(record_key(item_id), encode(updated, claim=None, claimed_at=None))
        if edit.rule is not None:
            pipe.zrem(DELIVERABLE_KEY, item_id)
            pipe.zadd(DUE_KEY, {item_id: updated.due_at.timestamp()})
        return True

    return await fenced(client, item_id, plan)


async def _detach_item(client: Redis, item_id: str, session_id: str) -> bool:
    """Clear one item's origin chat when it is ``session_id``, keeping a live claim."""

    def plan(pipe: Pipeline, state: WatchedState) -> bool:
        item, live_claim, claimed_at = state
        if item.session_id != session_id:
            return False
        detached = replace(item, session_id="")
        pipe.multi()
        pipe.set(record_key(item_id), encode(detached, claim=live_claim, claimed_at=claimed_at))
        return True

    try:
        return await fenced(client, item_id, plan)
    except ScheduleStoreError:
        # The claim path quarantines it when it falls due; failing here fails every delete.
        logger.exception(
            "undecodable schedule record on the detach path", extra={"item_id": item_id}
        )
        return False


async def detach_session(client: Redis, session_id: str) -> int:
    """Clear ``session_id`` on every live item made in it; a raced write is read again."""
    found: list[str] = []
    for key in (DUE_KEY, FIRING_KEY, DELIVERABLE_KEY):
        found.extend(await ids(client, key))
    changed = 0
    for item_id in dict.fromkeys(found):
        changed += await _detach_item(client, item_id, session_id)
    return changed


async def quarantine(client: Redis, item_id: str, raw: bytes | str) -> None:
    """Move an undecodable record to the dead-letter hash, so one item drops out of the pass."""
    logger.error(
        "quarantining a corrupt schedule record",
        extra={"item_id": item_id, "dead_key": DEAD_KEY},
    )
    async with client.pipeline(transaction=True) as pipe:
        pipe.hset(DEAD_KEY, item_id, raw)
        pipe.zrem(DUE_KEY, item_id)
        pipe.zrem(FIRING_KEY, item_id)
        pipe.zrem(DELIVERABLE_KEY, item_id)
        pipe.delete(record_key(item_id))
        await pipe.execute()


def _replaced(value: bytes | str) -> str:
    """Decode bytes for inspection, substituting replacement characters instead of raising."""
    return value if isinstance(value, str) else value.decode("utf-8", errors="replace")


async def dead_letters(client: Redis) -> tuple[DeadLetter, ...]:
    """The quarantined records in id order, for an operator to inspect."""
    raw = await client.hgetall(DEAD_KEY)
    letters = [
        DeadLetter(item_id=_replaced(field), raw=_replaced(value)) for field, value in raw.items()
    ]
    return tuple(sorted(letters, key=lambda letter: letter.item_id))


async def purge_dead_letter(client: Redis, item_id: str) -> bool:
    """Drop one quarantined record for good; False when nothing was quarantined under it."""
    removed = await client.hdel(DEAD_KEY, item_id)
    return removed > 0


async def _claim_one(
    client: Redis, item_id: str, now: datetime, lease: timedelta
) -> ScheduleClaim | None:
    """Move one eligible item to FIRING under a fresh token, the guard WATCH-fenced."""
    del lease
    async with client.pipeline(transaction=True) as pipe:
        await pipe.watch(record_key(item_id))
        raw = await pipe.get(record_key(item_id))
        if raw is None:
            # The index still lists an item whose record is gone; drop the index entries.
            pipe.multi()
            pipe.zrem(DUE_KEY, item_id)
            pipe.zrem(FIRING_KEY, item_id)
            with suppress(WatchError):
                await pipe.execute()
            return None
        try:
            item, _, _ = decode(raw, item_id)
        except ScheduleStoreError:
            logger.exception(
                "undecodable schedule record on the claim path", extra={"item_id": item_id}
            )
            await pipe.unwatch()
            await quarantine(client, item_id, raw)
            return None
        if item.status is ScheduleStatus.PENDING and item.due_at > now:
            # A snooze, or a finish that scheduled the next occurrence, moved the item forward
            # between the index snapshot `claim_due` read and this WATCH. WATCH only fences writes
            # made after it, so this re-read of the record closes that window.
            await pipe.unwatch()
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
    """Claim due PENDING items and lease-expired FIRING ones, oldest-due-first."""
    due = await ids(client, DUE_KEY, upto=now.timestamp(), limit=limit)
    expired = await ids(client, FIRING_KEY, upto=(now - lease).timestamp(), limit=limit)
    claims: list[ScheduleClaim] = []
    for item_id in dict.fromkeys(due + expired):
        claim = await _claim_one(client, item_id, now, lease)
        if claim is not None:
            claims.append(claim)
    claims.sort(key=lambda claim: claim.item.due_at)
    for surplus in claims[limit:]:
        await release_claim(client, surplus)
    return tuple(claims[:limit])
