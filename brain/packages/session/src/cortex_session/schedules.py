"""RedisScheduleStore: the ScheduleStore port over durable Redis keys (ADR-0025)."""

from collections.abc import Sequence
from datetime import datetime, timedelta

from redis.asyncio import Redis
from redis.exceptions import RedisError, WatchError

from cortex_core import (
    FireOutcome,
    ScheduleClaim,
    ScheduledItem,
    ScheduleEdit,
    ScheduleStatus,
    ScheduleStoreError,
    apply_snooze,
)
from cortex_session.schedule_claims import (
    claim_due,
    dead_letters,
    edit_item,
    ids,
    purge_dead_letter,
    release_claim,
    watched_state,
)
from cortex_session.schedule_codec import (
    DELIVERABLE_KEY,
    DUE_KEY,
    FIRING_KEY,
    DeadLetter,
    decode,
    encode,
    record_key,
)
from cortex_session.schedule_delivery import ack_item, deliverable_items, finish_claim
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
        """Return the item with ``item_id`` (None when unknown); a corrupt record raises."""
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

        A dangling index id (its record deleted) is skipped, the same tolerance
        ``list_sessions`` has; a present-but-corrupt record raises through ``decode``.
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
        """Delete the record and every index entry (False for unknown). It never decodes, so a
        corrupt record is cancellable too, and a cancel holds through an in-flight fire."""
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

    async def snooze(self, item_id: str, *, until: datetime) -> bool:
        """Postpone an item to ``until`` via ``apply_snooze``; FIRING and unknown answer False."""
        try:
            async with self._client.pipeline(transaction=True) as pipe:
                state = await watched_state(pipe, item_id)
                if state is None:
                    return False
                item, _, _ = state
                if item.status is ScheduleStatus.FIRING:
                    return False
                snoozed = apply_snooze(item, until)
                pipe.multi()
                pipe.zrem(DELIVERABLE_KEY, item_id)
                pipe.set(record_key(item_id), encode(snoozed, claim=None, claimed_at=None))
                pipe.zadd(DUE_KEY, {item_id: until.timestamp()})
                try:
                    await pipe.execute()
                except WatchError:
                    return False
        except RedisError as err:
            msg = f"snooze of schedule {item_id!r} failed"
            raise ScheduleStoreError(msg) from err
        return True

    async def edit(self, item_id: str, edit: ScheduleEdit) -> bool:
        """Retext / re-recur a non-FIRING item, WATCH-fenced (``schedule_claims.edit_item``)."""
        try:
            return await edit_item(self._client, item_id, edit)
        except RedisError as err:
            msg = f"edit of schedule {item_id!r} failed"
            raise ScheduleStoreError(msg) from err

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
        """Persist one fire under the claim's token (``schedule_delivery.finish_claim``)."""
        try:
            return await finish_claim(self._client, claim, outcome)
        except RedisError as err:
            msg = f"finish of schedule {claim.item.id!r} failed"
            raise ScheduleStoreError(msg) from err

    async def release(self, claim: ScheduleClaim) -> bool:
        """Un-claim (FIRING → PENDING, due unchanged); WATCH-fenced like ``finish``."""
        try:
            return await release_claim(self._client, claim)
        except RedisError as err:
            msg = f"release of schedule {claim.item.id!r} failed"
            raise ScheduleStoreError(msg) from err

    async def dead_letters(self) -> Sequence[DeadLetter]:
        """The quarantined records, for operator inspection (dead-letter addendum)."""
        try:
            return await dead_letters(self._client)
        except RedisError as err:
            msg = "listing dead-lettered schedules failed"
            raise ScheduleStoreError(msg) from err

    async def purge_dead_letter(self, item_id: str) -> bool:
        """Drop one quarantined record for good; False when it was not quarantined."""
        try:
            return await purge_dead_letter(self._client, item_id)
        except RedisError as err:
            msg = f"purging dead-lettered schedule {item_id!r} failed"
            raise ScheduleStoreError(msg) from err

    async def deliverable(self) -> Sequence[ScheduledItem]:
        """Fired reminders awaiting ack (``schedule_delivery.deliverable_items``)."""
        try:
            return await deliverable_items(self._client)
        except RedisError as err:
            msg = "listing deliverable reminders failed"
            raise ScheduleStoreError(msg) from err

    async def ack(self, item_id: str) -> bool:
        """Clear one fired reminder's delivery slot (``schedule_delivery.ack_item``)."""
        try:
            return await ack_item(self._client, item_id)
        except RedisError as err:
            msg = f"ack of reminder {item_id!r} failed"
            raise ScheduleStoreError(msg) from err
