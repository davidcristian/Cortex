"""RedisScheduleStore: the ScheduleStore port over durable Redis keys (ADR-0025).

The state a schedule outlives every model swap and brain restart through (the one hard rule);
key layout + codec policy in ``schedule_codec.py``, full contract in
``docs/modules/brain-session.md``. The adapter only translates: the fenced claim→finish
semantics live at the port; every backend failure crosses as ``ScheduleStoreError`` (cause
chained); an undecodable record on the CLAIM path is quarantined to the dead-letter hash (the
poison-pill defense) while targeted reads fail loudly naming the key; and every record+index
update runs as one MULTI/EXEC pipeline, so a crash cannot orphan a record from its indexes.
"""

import logging
from collections.abc import Sequence
from dataclasses import replace
from datetime import datetime, timedelta
from typing import cast
from uuid import uuid4

from redis.asyncio import Redis
from redis.exceptions import RedisError

from cortex_core import (
    FireOutcome,
    ScheduleClaim,
    ScheduledItem,
    ScheduleStatus,
    ScheduleStoreError,
)
from cortex_session.schedule_codec import (
    DEAD_KEY,
    DELIVERABLE_KEY,
    DUE_KEY,
    FIRING_KEY,
    decode,
    encode,
    record_key,
)
from cortex_session.store import DEFAULT_REDIS_URL

logger = logging.getLogger(__name__)


class RedisScheduleStore:
    """ScheduleStore adapter over redis-py asyncio (injected client or ``from_url``)."""

    def __init__(self, client: Redis) -> None:
        self._client = client

    @classmethod
    def from_url(cls, url: str = DEFAULT_REDIS_URL) -> "RedisScheduleStore":
        """Build a store owning a client for ``url``; close it via ``aclose()``."""
        return cls(Redis.from_url(url))  # pyright: ignore[reportUnknownMemberType]

    async def aclose(self) -> None:
        """Release the client's connections (call at composition-root shutdown)."""
        try:
            await self._client.aclose()
        except RedisError as err:
            msg = "closing the Redis client failed"
            raise ScheduleStoreError(msg) from err

    async def add(self, item: ScheduledItem) -> None:
        """Persist one fresh (PENDING) schedule and index it by due time."""
        try:
            async with self._client.pipeline(transaction=True) as pipe:
                pipe.set(record_key(item.id), encode(item, claim=None, claimed_at=None))
                pipe.zadd(DUE_KEY, {item.id: item.due_at.timestamp()})
                await pipe.execute()
        except RedisError as err:
            msg = f"add of schedule {item.id!r} failed"
            raise ScheduleStoreError(msg) from err

    async def get(self, item_id: str) -> ScheduledItem | None:
        """Return the item with ``item_id`` (None when unknown); corrupt records fail loudly."""
        try:
            raw = await self._client.get(record_key(item_id))
        except RedisError as err:
            msg = f"get of schedule {item_id!r} failed"
            raise ScheduleStoreError(msg) from err
        if raw is None:
            return None
        item, _, _ = decode(raw, item_id)
        return item

    async def _ids(self, key: str, *, upto: float | None = None, limit: int = 8) -> list[str]:
        """Members of one index ZSET, score order; score-bounded and counted when ``upto``."""
        if upto is None:
            # zrange's return type is partially Any in redis-py's typing (withscores overloads).
            raw = await self._client.zrange(key, 0, -1)  # pyright: ignore[reportUnknownMemberType]
        else:
            # zrangebyscore's return type is partially Any in redis-py's typing (overloads).
            raw = await self._client.zrangebyscore(  # pyright: ignore[reportUnknownMemberType]
                key, "-inf", upto, start=0, num=limit
            )
        return [member.decode("utf-8") for member in cast("list[bytes]", raw)]

    async def list_active(self) -> Sequence[ScheduledItem]:
        """PENDING/FIRING items plus fired-but-undelivered ones, due order.

        A dangling index id (its record deleted) is skipped, the ``list_sessions``
        tolerance; a present-but-corrupt record fails loudly via ``decode``.
        """
        try:
            ids: list[str] = []
            for key in (DUE_KEY, FIRING_KEY, DELIVERABLE_KEY):
                ids.extend(await self._ids(key))
            items: list[ScheduledItem] = []
            for item_id in dict.fromkeys(ids):
                raw = await self._client.get(record_key(item_id))
                if raw is not None:
                    item, _, _ = decode(raw, item_id)
                    items.append(item)
        except RedisError as err:
            msg = "listing active schedules failed"
            raise ScheduleStoreError(msg) from err
        return tuple(sorted(items, key=lambda item: item.due_at))

    async def cancel(self, item_id: str) -> bool:
        """Delete record + every index entry (False for unknown); never decodes, so a
        corrupt record is cancellable too. Cancel sticks through an in-flight fire."""
        try:
            async with self._client.pipeline(transaction=True) as pipe:
                pipe.zrem(DUE_KEY, item_id)
                pipe.zrem(FIRING_KEY, item_id)
                pipe.zrem(DELIVERABLE_KEY, item_id)
                pipe.delete(record_key(item_id))
                results = cast("list[int]", await pipe.execute())
        except RedisError as err:
            msg = f"cancel of schedule {item_id!r} failed"
            raise ScheduleStoreError(msg) from err
        return results[3] > 0

    async def _quarantine(self, item_id: str, raw: bytes | str) -> None:
        """Dead-letter an undecodable claimed record so the pass degrades by one item."""
        logger.error("quarantining corrupt schedule record %r to %r", item_id, DEAD_KEY)
        async with self._client.pipeline(transaction=True) as pipe:
            pipe.hset(DEAD_KEY, item_id, raw)
            pipe.zrem(DUE_KEY, item_id)
            pipe.zrem(FIRING_KEY, item_id)
            pipe.zrem(DELIVERABLE_KEY, item_id)
            pipe.delete(record_key(item_id))
            await pipe.execute()

    async def _claim_one(self, item_id: str, now: datetime) -> ScheduleClaim | None:
        """Move one eligible item to FIRING under a fresh token; quarantine if undecodable."""
        raw = await self._client.get(record_key(item_id))
        if raw is None:
            # A dangling index entry (e.g. a crash between EXECs long past); drop it.
            async with self._client.pipeline(transaction=True) as pipe:
                pipe.zrem(DUE_KEY, item_id)
                pipe.zrem(FIRING_KEY, item_id)
                await pipe.execute()
            return None
        try:
            item, _, _ = decode(raw, item_id)
        except ScheduleStoreError:
            logger.exception("undecodable schedule record on the claim path")
            await self._quarantine(item_id, raw)
            return None
        firing = replace(item, status=ScheduleStatus.FIRING)
        token = str(uuid4())
        async with self._client.pipeline(transaction=True) as pipe:
            pipe.set(record_key(item_id), encode(firing, claim=token, claimed_at=now))
            pipe.zrem(DUE_KEY, item_id)
            pipe.zadd(FIRING_KEY, {item_id: now.timestamp()})
            await pipe.execute()
        return ScheduleClaim(item=firing, token=token)

    async def claim_due(
        self, now: datetime, *, lease: timedelta, limit: int
    ) -> Sequence[ScheduleClaim]:
        """Claim due PENDING items and lease-expired FIRING ones, oldest-due-first.

        Candidates come capped from both indexes, so up to ``2 * limit`` are claimed and
        the overflow past ``limit`` (by due order) is released again. A bounded surplus
        at personal scale, and simpler than ranking across two differently-scored ZSETs.
        """
        try:
            due = await self._ids(DUE_KEY, upto=now.timestamp(), limit=limit)
            expired = await self._ids(FIRING_KEY, upto=(now - lease).timestamp(), limit=limit)
            claims: list[ScheduleClaim] = []
            for item_id in dict.fromkeys(due + expired):
                claim = await self._claim_one(item_id, now)
                if claim is not None:
                    claims.append(claim)
            claims.sort(key=lambda claim: claim.item.due_at)
            for surplus in claims[limit:]:
                await self.release(surplus)
            return tuple(claims[:limit])
        except RedisError as err:
            msg = "claiming due schedules failed"
            raise ScheduleStoreError(msg) from err

    async def _held(self, claim: ScheduleClaim) -> ScheduledItem | None:
        """The item iff ``claim`` is its current claim (present, FIRING, token match)."""
        raw = await self._client.get(record_key(claim.item.id))
        if raw is None:
            return None
        item, live_token, _ = decode(raw, claim.item.id)
        if item.status is not ScheduleStatus.FIRING or live_token != claim.token:
            return None
        return item

    async def finish(self, claim: ScheduleClaim, outcome: FireOutcome) -> bool:
        """Persist one fire under the claim's token; a stale claimant no-ops False.

        Fire-time taint ORs onto the item; ``next_due`` re-arms PENDING, ``None`` is
        terminal, meaning DONE while deliverable, deleted otherwise (terminal cleanup).
        """
        try:
            item = await self._held(claim)
            if item is None:
                return False
            since = outcome.fired_at if outcome.deliverable else item.deliverable_since
            rearmed = outcome.next_due is not None
            updated = replace(
                item,
                status=ScheduleStatus.PENDING if rearmed else ScheduleStatus.DONE,
                due_at=outcome.next_due if outcome.next_due is not None else item.due_at,
                tainted=item.tainted or outcome.tainted,
                deliverable_since=since,
                last_outcome=outcome.outcome,
            )
            async with self._client.pipeline(transaction=True) as pipe:
                pipe.zrem(FIRING_KEY, claim.item.id)
                if since is not None:
                    pipe.zadd(DELIVERABLE_KEY, {claim.item.id: since.timestamp()})
                if outcome.next_due is not None:
                    pipe.set(record_key(item.id), encode(updated, claim=None, claimed_at=None))
                    pipe.zadd(DUE_KEY, {item.id: outcome.next_due.timestamp()})
                elif since is not None:
                    pipe.set(record_key(item.id), encode(updated, claim=None, claimed_at=None))
                else:
                    pipe.delete(record_key(item.id))
                await pipe.execute()
        except RedisError as err:
            msg = f"finish of schedule {claim.item.id!r} failed"
            raise ScheduleStoreError(msg) from err
        return True

    async def release(self, claim: ScheduleClaim) -> bool:
        """Un-claim (FIRING → PENDING, due unchanged) under the token; stale no-ops False."""
        try:
            item = await self._held(claim)
            if item is None:
                return False
            pending = replace(item, status=ScheduleStatus.PENDING)
            async with self._client.pipeline(transaction=True) as pipe:
                pipe.set(record_key(item.id), encode(pending, claim=None, claimed_at=None))
                pipe.zrem(FIRING_KEY, item.id)
                pipe.zadd(DUE_KEY, {item.id: item.due_at.timestamp()})
                await pipe.execute()
        except RedisError as err:
            msg = f"release of schedule {claim.item.id!r} failed"
            raise ScheduleStoreError(msg) from err
        return True

    async def deliverable(self) -> Sequence[ScheduledItem]:
        """Fired reminders awaiting ack, oldest-fired-first (dangling ids skipped)."""
        try:
            items: list[ScheduledItem] = []
            for item_id in await self._ids(DELIVERABLE_KEY):
                raw = await self._client.get(record_key(item_id))
                if raw is not None:
                    item, _, _ = decode(raw, item_id)
                    items.append(item)
        except RedisError as err:
            msg = "listing deliverable reminders failed"
            raise ScheduleStoreError(msg) from err
        return tuple(items)

    async def ack(self, item_id: str) -> bool:
        """Clear deliverability; a DONE one-shot is deleted. False when not deliverable."""
        try:
            raw = await self._client.get(record_key(item_id))
            if raw is None:
                return False
            item, claim, claimed_at = decode(raw, item_id)
            if item.deliverable_since is None:
                return False
            async with self._client.pipeline(transaction=True) as pipe:
                pipe.zrem(DELIVERABLE_KEY, item_id)
                if item.status is ScheduleStatus.DONE:
                    pipe.delete(record_key(item_id))
                else:
                    cleared = replace(item, deliverable_since=None)
                    pipe.set(
                        record_key(item_id), encode(cleared, claim=claim, claimed_at=claimed_at)
                    )
                await pipe.execute()
        except RedisError as err:
            msg = f"ack of reminder {item_id!r} failed"
            raise ScheduleStoreError(msg) from err
        return True
