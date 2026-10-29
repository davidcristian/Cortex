"""The RedisScheduleStore's post-fire path: settle a claim, then deliver and clear."""

from dataclasses import replace
from datetime import datetime

from redis.asyncio import Redis
from redis.asyncio.client import Pipeline

from cortex_core import (
    FireOutcome,
    ScheduleClaim,
    ScheduledItem,
    ScheduleStatus,
    acks_fire,
)
from cortex_session.schedule_claims import WatchedState, fenced, holds, ids, listed
from cortex_session.schedule_codec import (
    DELIVERABLE_KEY,
    DUE_KEY,
    FIRING_KEY,
    encode,
    record_key,
)


async def finish_claim(client: Redis, claim: ScheduleClaim, outcome: FireOutcome) -> bool:
    """Persist one fire under the claim's token; False once a cancel or a new claim took it."""

    def plan(pipe: Pipeline, state: WatchedState) -> bool:
        if not holds(state, claim):
            return False
        item = state[0]
        since = outcome.fired_at if outcome.deliverable else item.deliverable_since
        due = item.due_at if outcome.deliverable else item.deliverable_due_at
        started = outcome.started_at if outcome.deliverable else item.deliverable_started_at
        rearmed = outcome.next_due is not None
        updated = replace(
            item,
            status=ScheduleStatus.PENDING if rearmed else ScheduleStatus.DONE,
            due_at=outcome.next_due if outcome.next_due is not None else item.due_at,
            tainted=item.tainted or outcome.tainted,
            deliverable_since=since,
            deliverable_due_at=due,
            deliverable_started_at=started,
            last_outcome=outcome.outcome,
        )
        pipe.multi()
        pipe.zrem(FIRING_KEY, item.id)
        if since is not None:
            pipe.zadd(DELIVERABLE_KEY, {item.id: since.timestamp()})
        if outcome.next_due is not None:
            pipe.set(record_key(item.id), encode(updated, claim=None, claimed_at=None))
            pipe.zadd(DUE_KEY, {item.id: outcome.next_due.timestamp()})
        elif since is not None:
            pipe.set(record_key(item.id), encode(updated, claim=None, claimed_at=None))
        else:
            pipe.delete(record_key(item.id))
        return True

    return await fenced(client, claim.item.id, plan)


async def deliverable_items(client: Redis) -> tuple[ScheduledItem, ...]:
    """Fired reminders awaiting ack, oldest-fired-first (dangling and corrupt ids skipped)."""
    items: list[ScheduledItem] = []
    for item_id in await ids(client, DELIVERABLE_KEY):
        item = await listed(client, item_id)
        if item is not None:
            items.append(item)
    return tuple(items)


async def ack_item(client: Redis, item_id: str, fired_at: datetime | None) -> bool:
    """Clear the fire ``fired_at`` names; a DONE one-shot is deleted."""

    def plan(pipe: Pipeline, state: WatchedState) -> bool:
        item, live_claim, claimed_at = state
        if not acks_fire(item, fired_at):
            return False
        pipe.multi()
        pipe.zrem(DELIVERABLE_KEY, item_id)
        if item.status is ScheduleStatus.DONE:
            pipe.delete(record_key(item_id))
        else:
            cleared = replace(
                item, deliverable_since=None, deliverable_due_at=None, deliverable_started_at=None
            )
            pipe.set(
                record_key(item_id),
                encode(cleared, claim=live_claim, claimed_at=claimed_at),
            )
        return True

    return await fenced(client, item_id, plan)
