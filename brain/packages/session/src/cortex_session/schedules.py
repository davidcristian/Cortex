"""RedisScheduleStore: the ScheduleStore port over durable Redis keys (ADR-0025).

The state a schedule outlives every model swap and brain restart through (the one hard rule);
key layout + codec policy in ``schedule_codec.py``, the claim path + WATCH-fenced transition
helpers in ``schedule_claims.py``, full contract in ``docs/modules/brain-session.md``. The
adapter only translates: the fenced claim→finish semantics live at the port; **every guarded
transition is optimistically atomic** (WATCH→MULTI/EXEC, so a racing ``cancel``/``ack``/claim
makes the write's EXEC fail as ``WatchError``, answered like a stale token, post-review
hardening); every backend failure crosses as ``ScheduleStoreError`` (cause chained); an
undecodable record on the CLAIM path is quarantined to the dead-letter hash (the poison-pill
defense) while targeted reads fail loudly naming the key.
"""

from collections.abc import Sequence
from dataclasses import replace
from datetime import datetime, timedelta

from redis.asyncio import Redis
from redis.exceptions import RedisError, WatchError

from cortex_core import (
    FireOutcome,
    ScheduleClaim,
    ScheduledItem,
    ScheduleStatus,
    ScheduleStoreError,
)
from cortex_session.schedule_claims import claim_due, ids, release_claim, watched_state
from cortex_session.schedule_codec import (
    DELIVERABLE_KEY,
    DUE_KEY,
    FIRING_KEY,
    decode,
    encode,
    record_key,
)
from cortex_session.store import DEFAULT_REDIS_URL


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

    async def list_active(self) -> Sequence[ScheduledItem]:
        """PENDING/FIRING items plus fired-but-undelivered ones, due order.

        A dangling index id (its record deleted) is skipped, the ``list_sessions``
        tolerance; a present-but-corrupt record fails loudly via ``decode``.
        """
        try:
            found: list[str] = []
            for key in (DUE_KEY, FIRING_KEY, DELIVERABLE_KEY):
                found.extend(await ids(self._client, key))
            items: list[ScheduledItem] = []
            for item_id in dict.fromkeys(found):
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
                results = await pipe.execute()
        except RedisError as err:
            msg = f"cancel of schedule {item_id!r} failed"
            raise ScheduleStoreError(msg) from err
        deleted: int = results[3]
        return deleted > 0

    async def claim_due(
        self, now: datetime, *, lease: timedelta, limit: int
    ) -> Sequence[ScheduleClaim]:
        """Claim due PENDING + lease-expired FIRING items (``schedule_claims.claim_due``)."""
        try:
            return await claim_due(self._client, now, lease=lease, limit=limit)
        except RedisError as err:
            msg = "claiming due schedules failed"
            raise ScheduleStoreError(msg) from err

    async def finish(self, claim: ScheduleClaim, outcome: FireOutcome) -> bool:
        """Persist one fire under the claim's token; a stale or raced claimant no-ops False.

        Fire-time taint ORs onto the item; ``next_due`` re-arms PENDING, ``None`` is
        terminal, meaning DONE while deliverable, deleted otherwise (terminal cleanup). The guard
        and the write share one WATCH transaction: a cancel/ack landing between them makes
        the EXEC fail, so nothing a user was told is undone (post-review hardening).
        """
        try:
            async with self._client.pipeline(transaction=True) as pipe:
                state = await watched_state(pipe, claim.item.id)
                if state is None:
                    return False
                item, live_token, _ = state
                if item.status is not ScheduleStatus.FIRING or live_token != claim.token:
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
                pipe.multi()
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
                try:
                    await pipe.execute()
                except WatchError:
                    return False
        except RedisError as err:
            msg = f"finish of schedule {claim.item.id!r} failed"
            raise ScheduleStoreError(msg) from err
        return True

    async def release(self, claim: ScheduleClaim) -> bool:
        """Un-claim (FIRING → PENDING, due unchanged); WATCH-fenced like ``finish``."""
        try:
            return await release_claim(self._client, claim)
        except RedisError as err:
            msg = f"release of schedule {claim.item.id!r} failed"
            raise ScheduleStoreError(msg) from err

    async def deliverable(self) -> Sequence[ScheduledItem]:
        """Fired reminders awaiting ack, oldest-fired-first (dangling ids skipped)."""
        try:
            items: list[ScheduledItem] = []
            for item_id in await ids(self._client, DELIVERABLE_KEY):
                raw = await self._client.get(record_key(item_id))
                if raw is not None:
                    item, _, _ = decode(raw, item_id)
                    items.append(item)
        except RedisError as err:
            msg = "listing deliverable reminders failed"
            raise ScheduleStoreError(msg) from err
        return tuple(items)

    async def ack(self, item_id: str) -> bool:
        """Clear deliverability; a DONE one-shot is deleted. False when not deliverable.

        WATCH-fenced: an ack racing a re-claim (or cancel) fails its EXEC instead of
        writing back the stale claim state it read (post-review hardening).
        """
        try:
            async with self._client.pipeline(transaction=True) as pipe:
                state = await watched_state(pipe, item_id)
                if state is None:
                    return False
                item, live_claim, claimed_at = state
                if item.deliverable_since is None:
                    return False
                pipe.multi()
                pipe.zrem(DELIVERABLE_KEY, item_id)
                if item.status is ScheduleStatus.DONE:
                    pipe.delete(record_key(item_id))
                else:
                    cleared = replace(item, deliverable_since=None)
                    pipe.set(
                        record_key(item_id),
                        encode(cleared, claim=live_claim, claimed_at=claimed_at),
                    )
                try:
                    await pipe.execute()
                except WatchError:
                    return False
        except RedisError as err:
            msg = f"ack of reminder {item_id!r} failed"
            raise ScheduleStoreError(msg) from err
        return True
