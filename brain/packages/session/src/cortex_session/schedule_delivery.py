"""The RedisScheduleStore's post-fire path: settle a claim, then deliver and clear (ADR-0025).

Split from ``schedules.py`` by responsibility (the 300-line cap), the same shape
``schedule_claims.py`` took: module functions over the injected client, with ``schedules.py``
delegating and owning the ``RedisError``→``ScheduleStoreError`` wrapping at the port edge.
Where ``schedule_claims.py`` owns everything up to and including the claim, this module owns
everything after the fire: ``finish_claim`` records one outcome under the claim's token,
``deliverable_items`` lists what the fire left awaiting the user, and ``ack_item`` clears it.

Every transition here is optimistically atomic for the reason the claim path is: the token or
deliverability guard and the state write share one WATCH→MULTI/EXEC transaction, so a
``cancel``/``ack``/re-claim landing between them fails the ``EXEC`` as ``WatchError`` and is
answered like a stale token (``False``) rather than overwriting what the other transition wrote.
"""

from dataclasses import replace

from redis.asyncio import Redis
from redis.exceptions import WatchError

from cortex_core import (
    FireOutcome,
    ScheduleClaim,
    ScheduledItem,
    ScheduleStatus,
)
from cortex_session.schedule_claims import ids, watched_state
from cortex_session.schedule_codec import (
    DELIVERABLE_KEY,
    DUE_KEY,
    FIRING_KEY,
    decode,
    encode,
    record_key,
)


async def finish_claim(client: Redis, claim: ScheduleClaim, outcome: FireOutcome) -> bool:
    """Persist one fire under the claim's token; a stale or raced claimant no-ops False.

    Fire-time taint is ORed onto the item; ``next_due`` re-arms the item PENDING, and ``None``
    is terminal, meaning DONE while deliverable and deleted otherwise (terminal cleanup). The
    guard and the write share one WATCH transaction: a cancel or ack landing between them makes
    the EXEC fail, so nothing a user was told is undone (post-review hardening).
    """
    async with client.pipeline(transaction=True) as pipe:
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
    return True


async def deliverable_items(client: Redis) -> tuple[ScheduledItem, ...]:
    """Fired reminders awaiting ack, oldest-fired-first (dangling ids skipped)."""
    items: list[ScheduledItem] = []
    for item_id in await ids(client, DELIVERABLE_KEY):
        raw = await client.get(record_key(item_id))
        if raw is not None:
            item, _, _ = decode(raw, item_id)
            items.append(item)
    return tuple(items)


async def ack_item(client: Redis, item_id: str) -> bool:
    """Clear deliverability; a DONE one-shot is deleted. False when not deliverable.

    WATCH-fenced: an ack racing a re-claim (or cancel) fails its EXEC instead of
    writing back the stale claim state it read (post-review hardening).
    """
    async with client.pipeline(transaction=True) as pipe:
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
    return True
