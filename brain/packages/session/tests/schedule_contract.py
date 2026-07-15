"""Shared ScheduleStore behavior checks. Every implementation must pass all of them.

Driven by the parametrized contract test (in-memory fake + fakeredis-backed Redis adapter).
The two must be observably interchangeable behind the port (ports-before-adapters, ADR-0025).
The fenced claim→finish protocol is the point of this suite: stale finishes are rejected,
cancel sticks through an in-flight fire, terminal items are cleaned up, taint ORs forward.
"""

from dataclasses import replace
from datetime import UTC, datetime, timedelta, timezone
from uuid import uuid4

from cortex_core import (
    CalendarRule,
    FireOutcome,
    MonthDay,
    MonthDays,
    RuleChange,
    ScheduledItem,
    ScheduleEdit,
    ScheduleKind,
    ScheduleStatus,
    ScheduleStore,
    Weekdays,
    YearDays,
)

_NOW = datetime(2026, 7, 12, 12, 0, 0, tzinfo=UTC)
_LEASE = timedelta(minutes=5)


def _item_id() -> str:
    return f"contract-{uuid4()}"


def make_item(
    item_id: str,
    *,
    kind: ScheduleKind = ScheduleKind.REMINDER,
    due_at: datetime = _NOW,
    every: timedelta | None = None,
    model: str = "",
    tainted: bool = False,
) -> ScheduledItem:
    return ScheduledItem(
        id=item_id,
        kind=kind,
        text="stretch your legs",
        session_id="session-1",
        due_at=due_at,
        created_at=_NOW - timedelta(hours=1),
        every=every,
        model=model,
        tainted=tainted,
    )


async def check_missing_get_is_none(store: ScheduleStore) -> None:
    """An unknown id reads back as None, not an error."""
    assert await store.get(_item_id()) is None


async def check_add_get_round_trips(store: ScheduleStore) -> None:
    """A stored item reads back field-for-field, provenance and hints included."""
    item = make_item(
        _item_id(),
        kind=ScheduleKind.TASK,
        every=timedelta(hours=2),
        model="fast",
        tainted=True,
    )
    await store.add(item)
    assert await store.get(item.id) == item


async def check_timezone_fidelity(store: ScheduleStore) -> None:
    """A non-UTC timestamp survives the round-trip with its offset intact."""
    offset = timezone(timedelta(hours=5, minutes=30))
    item = make_item(_item_id(), due_at=datetime(2026, 7, 12, 17, 45, tzinfo=offset))
    await store.add(item)
    loaded = await store.get(item.id)
    assert loaded is not None
    assert loaded.due_at.utcoffset() == timedelta(hours=5, minutes=30)


async def check_list_active_orders_by_due(store: ScheduleStore) -> None:
    """list_active returns pending items in due order."""
    later = make_item(_item_id(), due_at=_NOW + timedelta(hours=2))
    sooner = make_item(_item_id(), due_at=_NOW + timedelta(hours=1))
    await store.add(later)
    await store.add(sooner)
    listed = await store.list_active()
    assert [item.id for item in listed] == [sooner.id, later.id]


async def check_cancel_semantics(store: ScheduleStore) -> None:
    """cancel removes a pending item (True); an unknown id is False."""
    item = make_item(_item_id())
    await store.add(item)
    assert await store.cancel(item.id) is True
    assert await store.get(item.id) is None
    assert await store.list_active() == ()
    assert await store.cancel(item.id) is False


async def check_claim_due_boundary(store: ScheduleStore) -> None:
    """An item due exactly at now is claimable; a future item is not."""
    due = make_item(_item_id(), due_at=_NOW)
    future = make_item(_item_id(), due_at=_NOW + timedelta(seconds=1))
    await store.add(due)
    await store.add(future)
    claims = await store.claim_due(_NOW, lease=_LEASE, limit=10)
    assert [claim.item.id for claim in claims] == [due.id]
    assert claims[0].item.status is ScheduleStatus.FIRING


async def check_claim_due_limit_and_order(store: ScheduleStore) -> None:
    """More eligible items than limit: the oldest-due win, the rest stay claimable."""
    third = make_item(_item_id(), due_at=_NOW - timedelta(minutes=1))
    first = make_item(_item_id(), due_at=_NOW - timedelta(minutes=3))
    second = make_item(_item_id(), due_at=_NOW - timedelta(minutes=2))
    for item in (third, first, second):
        await store.add(item)
    claims = await store.claim_due(_NOW, lease=_LEASE, limit=2)
    assert [claim.item.id for claim in claims] == [first.id, second.id]
    rest = await store.claim_due(_NOW, lease=_LEASE, limit=2)
    assert [claim.item.id for claim in rest] == [third.id]


async def check_claimed_item_is_not_reclaimable_within_lease(store: ScheduleStore) -> None:
    """A FIRING item stays claimed until its lease expires."""
    item = make_item(_item_id())
    await store.add(item)
    assert len(await store.claim_due(_NOW, lease=_LEASE, limit=10)) == 1
    again = await store.claim_due(_NOW + timedelta(seconds=30), lease=_LEASE, limit=10)
    assert again == ()


async def check_lease_expiry_reclaims_with_a_fresh_token(store: ScheduleStore) -> None:
    """A lease-expired FIRING item is re-claimed under a new fencing token."""
    item = make_item(_item_id())
    await store.add(item)
    (first,) = await store.claim_due(_NOW, lease=_LEASE, limit=10)
    (second,) = await store.claim_due(_NOW + _LEASE, lease=_LEASE, limit=10)
    assert second.item.id == item.id
    assert second.token != first.token


async def check_stale_finish_is_rejected(store: ScheduleStore) -> None:
    """The original claimant's late finish no-ops after a re-claim (the fencing token)."""
    item = make_item(_item_id(), every=timedelta(hours=1))
    await store.add(item)
    (stale,) = await store.claim_due(_NOW, lease=_LEASE, limit=10)
    (live,) = await store.claim_due(_NOW + _LEASE, lease=_LEASE, limit=10)
    outcome = FireOutcome(
        fired_at=_NOW + _LEASE, next_due=_NOW + timedelta(hours=9), deliverable=True
    )
    assert await store.finish(stale, outcome) is False
    loaded = await store.get(item.id)
    assert loaded is not None
    assert loaded.status is ScheduleStatus.FIRING  # the stale finish changed nothing
    assert loaded.deliverable_since is None
    assert await store.finish(live, outcome) is True


async def check_finish_rearms_a_recurring_item(store: ScheduleStore) -> None:
    """next_due re-arms PENDING at the new time, outcome recorded, claim cleared."""
    item = make_item(_item_id(), kind=ScheduleKind.TASK, every=timedelta(hours=1))
    await store.add(item)
    (claim,) = await store.claim_due(_NOW, lease=_LEASE, limit=10)
    rearm_at = _NOW + timedelta(hours=1)
    done = FireOutcome(
        fired_at=_NOW, next_due=rearm_at, deliverable=False, outcome="[subagent 1] ok"
    )
    assert await store.finish(claim, done) is True
    loaded = await store.get(item.id)
    assert loaded is not None
    assert loaded.status is ScheduleStatus.PENDING
    assert loaded.due_at == rearm_at
    assert loaded.last_outcome == "[subagent 1] ok"
    assert await store.claim_due(_NOW + timedelta(minutes=30), lease=_LEASE, limit=10) == ()
    reclaims = await store.claim_due(rearm_at, lease=_LEASE, limit=10)
    assert [claim.item.id for claim in reclaims] == [item.id]


async def check_finish_terminal_without_delivery_deletes(store: ScheduleStore) -> None:
    """A one-shot task's terminal finish deletes the record (terminal cleanup)."""
    item = make_item(_item_id(), kind=ScheduleKind.TASK)
    await store.add(item)
    (claim,) = await store.claim_due(_NOW, lease=_LEASE, limit=10)
    outcome = FireOutcome(fired_at=_NOW, next_due=None, deliverable=False, outcome="done")
    assert await store.finish(claim, outcome) is True
    assert await store.get(item.id) is None
    assert await store.list_active() == ()


async def check_one_shot_reminder_delivery_lifecycle(store: ScheduleStore) -> None:
    """Fired one-shot reminder: DONE + deliverable + still active; ack deletes it."""
    item = make_item(_item_id())
    await store.add(item)
    (claim,) = await store.claim_due(_NOW, lease=_LEASE, limit=10)
    fired = FireOutcome(fired_at=_NOW, next_due=None, deliverable=True)
    assert await store.finish(claim, fired) is True
    (due,) = await store.deliverable()
    assert due.id == item.id
    assert due.status is ScheduleStatus.DONE
    assert due.deliverable_since == _NOW
    assert [listed.id for listed in await store.list_active()] == [item.id]
    assert await store.ack(item.id) is True
    assert await store.deliverable() == ()
    assert await store.get(item.id) is None
    assert await store.ack(item.id) is False


async def check_recurring_reminder_coalesces_delivery(store: ScheduleStore) -> None:
    """A recurring reminder re-arms AND stays deliverable; ack clears only delivery."""
    item = make_item(_item_id(), every=timedelta(hours=1))
    await store.add(item)
    (claim,) = await store.claim_due(_NOW, lease=_LEASE, limit=10)
    rearm_at = _NOW + timedelta(hours=1)
    fired = FireOutcome(fired_at=_NOW, next_due=rearm_at, deliverable=True)
    assert await store.finish(claim, fired) is True
    (due,) = await store.deliverable()
    assert due.status is ScheduleStatus.PENDING
    assert due.deliverable_since == _NOW
    assert await store.ack(item.id) is True
    loaded = await store.get(item.id)
    assert loaded is not None
    assert loaded.deliverable_since is None
    assert loaded.due_at == rearm_at


async def check_fire_taint_ors_onto_the_item(store: ScheduleStore) -> None:
    """A clean-created item whose fire consumed untrusted content becomes tainted."""
    item = make_item(_item_id(), kind=ScheduleKind.TASK, every=timedelta(hours=1))
    await store.add(item)
    (claim,) = await store.claim_due(_NOW, lease=_LEASE, limit=10)
    outcome = FireOutcome(
        fired_at=_NOW,
        next_due=_NOW + timedelta(hours=1),
        deliverable=False,
        outcome="the file said hi",
        tainted=True,
    )
    assert await store.finish(claim, outcome) is True
    loaded = await store.get(item.id)
    assert loaded is not None
    assert loaded.tainted is True


async def check_cancel_sticks_through_an_in_flight_fire(store: ScheduleStore) -> None:
    """cancel during FIRING wins: the fire's later finish no-ops and nothing re-arms."""
    item = make_item(_item_id(), every=timedelta(hours=1))
    await store.add(item)
    (claim,) = await store.claim_due(_NOW, lease=_LEASE, limit=10)
    assert await store.cancel(item.id) is True
    outcome = FireOutcome(fired_at=_NOW, next_due=_NOW + timedelta(hours=1), deliverable=True)
    assert await store.finish(claim, outcome) is False
    assert await store.release(claim) is False  # the un-claim path is equally dead
    assert await store.get(item.id) is None
    assert await store.list_active() == ()
    assert await store.deliverable() == ()


async def check_cancel_clears_a_deliverable_reminder(store: ScheduleStore) -> None:
    """cancel of a fired-but-undelivered one-shot stops it surfacing (True)."""
    item = make_item(_item_id())
    await store.add(item)
    (claim,) = await store.claim_due(_NOW, lease=_LEASE, limit=10)
    fired = FireOutcome(fired_at=_NOW, next_due=None, deliverable=True)
    assert await store.finish(claim, fired) is True
    assert await store.cancel(item.id) is True
    assert await store.deliverable() == ()
    assert await store.list_active() == ()


async def check_release_returns_the_item_to_pending(store: ScheduleStore) -> None:
    """release un-claims (due unchanged) so the item is immediately claimable again."""
    item = make_item(_item_id())
    await store.add(item)
    (claim,) = await store.claim_due(_NOW, lease=_LEASE, limit=10)
    assert await store.release(claim) is True
    loaded = await store.get(item.id)
    assert loaded is not None
    assert loaded.status is ScheduleStatus.PENDING
    assert loaded.due_at == item.due_at
    # The released claim is dead: neither finish nor release applies to a PENDING item.
    outcome = FireOutcome(fired_at=_NOW, next_due=None, deliverable=True)
    assert await store.finish(claim, outcome) is False
    (again,) = await store.claim_due(_NOW, lease=_LEASE, limit=10)
    assert again.item.id == item.id
    assert await store.release(claim) is False  # the old token is stale now


async def check_claim_orders_across_both_classes(store: ScheduleStore) -> None:
    """Oldest-due-first spans due PENDING and lease-expired FIRING items together."""
    older = make_item(_item_id(), due_at=_NOW - timedelta(minutes=10))
    await store.add(older)
    (first,) = await store.claim_due(_NOW - _LEASE, lease=_LEASE, limit=10)
    newer = make_item(_item_id(), due_at=_NOW - timedelta(minutes=2))
    await store.add(newer)
    # One slot, one candidate per class: the older due (the lease-expired FIRING) wins.
    (winner,) = await store.claim_due(_NOW, lease=_LEASE, limit=1)
    assert winner.item.id == older.id
    assert winner.token != first.token
    (second,) = await store.claim_due(_NOW, lease=_LEASE, limit=1)
    assert second.item.id == newer.id


async def check_ack_requires_deliverability(store: ScheduleStore) -> None:
    """ack of a pending or unknown item is False."""
    item = make_item(_item_id())
    await store.add(item)
    assert await store.ack(item.id) is False
    assert await store.ack(_item_id()) is False


async def check_deliverable_lists_oldest_fired_first(store: ScheduleStore) -> None:
    """Two fired reminders list in fired order."""
    second = make_item(_item_id(), due_at=_NOW - timedelta(minutes=1))
    first = make_item(_item_id(), due_at=_NOW - timedelta(minutes=2))
    await store.add(second)
    await store.add(first)
    claims = {claim.item.id: claim for claim in await store.claim_due(_NOW, lease=_LEASE, limit=10)}
    later = FireOutcome(fired_at=_NOW + timedelta(seconds=2), next_due=None, deliverable=True)
    earlier = FireOutcome(fired_at=_NOW + timedelta(seconds=1), next_due=None, deliverable=True)
    assert await store.finish(claims[second.id], later) is True
    assert await store.finish(claims[first.id], earlier) is True
    listed = await store.deliverable()
    assert [item.id for item in listed] == [first.id, second.id]


async def check_snooze_moves_a_pending_one_shot(store: ScheduleStore) -> None:
    """snooze re-dues a PENDING one-shot: not claimable at the old time, claimable at the new."""
    item = make_item(_item_id())
    await store.add(item)
    until = _NOW + timedelta(minutes=30)
    assert await store.snooze(item.id, until=until) is True
    loaded = await store.get(item.id)
    assert loaded is not None
    assert loaded.status is ScheduleStatus.PENDING
    assert loaded.due_at == until
    assert await store.claim_due(_NOW, lease=_LEASE, limit=10) == ()
    (claim,) = await store.claim_due(until, lease=_LEASE, limit=10)
    assert claim.item.id == item.id


async def check_snooze_rearms_a_deliverable_reminder(store: ScheduleStore) -> None:
    """snooze of a fired-but-undelivered one-shot re-arms it: it fires fresh, not re-delivers."""
    item = make_item(_item_id())
    await store.add(item)
    (claim,) = await store.claim_due(_NOW, lease=_LEASE, limit=10)
    fired = FireOutcome(fired_at=_NOW, next_due=None, deliverable=True)
    assert await store.finish(claim, fired) is True
    until = _NOW + timedelta(minutes=10)
    assert await store.snooze(item.id, until=until) is True
    assert await store.deliverable() == ()
    assert await store.ack(item.id) is False  # nothing awaits delivery any more
    loaded = await store.get(item.id)
    assert loaded is not None
    assert loaded.status is ScheduleStatus.PENDING
    assert loaded.deliverable_since is None
    (again,) = await store.claim_due(until, lease=_LEASE, limit=10)
    assert again.item.id == item.id


async def check_snooze_preserves_a_recurring_grid(store: ScheduleStore) -> None:
    """Snoozing a recurring item moves only the next occurrence; ``anchor`` pins the grid origin.

    The stored anchor round-trips the codec (the Redis leg exercises encode/decode of the new
    field), and the item becomes claimable at the snoozed time, not the original one.
    """
    item = make_item(_item_id(), every=timedelta(hours=1))  # due at _NOW
    await store.add(item)
    until = _NOW + timedelta(minutes=30)
    assert await store.snooze(item.id, until=until) is True
    loaded = await store.get(item.id)
    assert loaded is not None
    assert loaded.due_at == until  # the single occurrence moved
    assert loaded.anchor == _NOW  # the grid origin is pinned to the original due
    assert loaded.every == timedelta(hours=1)  # still recurring
    assert await store.claim_due(_NOW, lease=_LEASE, limit=10) == ()  # not due at the old time
    (claim,) = await store.claim_due(until, lease=_LEASE, limit=10)
    assert claim.item.id == item.id


async def check_a_calendar_rule_round_trips_and_needs_no_anchor(store: ScheduleStore) -> None:
    """A wall-clock rule survives the store, and a snooze leaves it self-anchoring.

    The Redis leg exercises the codec's additive ``rule`` key end to end (encode, store,
    decode). Unlike an interval item, a snoozed calendar item takes NO anchor: its rule is
    the recurrence grid, so nothing has to be pinned for the series to recover.
    """
    rule = CalendarRule(hour=9, minute=0, on=Weekdays(days=frozenset({0, 4})))
    item = replace(make_item(_item_id()), rule=rule)
    await store.add(item)
    loaded = await store.get(item.id)
    assert loaded is not None
    assert loaded.rule == rule
    assert loaded.every is None
    until = _NOW + timedelta(minutes=30)
    assert await store.snooze(item.id, until=until) is True
    snoozed = await store.get(item.id)
    assert snoozed is not None
    assert snoozed.rule == rule
    assert snoozed.anchor is None


async def check_a_month_day_rule_round_trips(store: ScheduleStore) -> None:
    """The monthly selector survives the store, which is the codec's other rule shape.

    The Redis leg is what this exists for: a monthly rule writes ``month_days`` where a weekly
    one writes ``days``, so only a real encode/store/decode proves the two do not collapse
    into each other (ADR-0025 monthly addendum).
    """
    rule = CalendarRule(hour=9, minute=0, on=MonthDays(days=frozenset({1, 15})))
    item = replace(make_item(_item_id()), rule=rule)
    await store.add(item)
    loaded = await store.get(item.id)
    assert loaded is not None
    assert loaded.rule == rule
    assert loaded.every is None


async def check_a_year_date_rule_round_trips(store: ScheduleStore) -> None:
    """The yearly selector survives the store, the codec's third and last rule shape.

    The Redis leg is what this exists for: a yearly rule writes ``year_dates`` as
    ``[month, day]`` pairs where its two siblings write flat day lists, so only a real
    encode/store/decode proves the pairs survive JSON and that the three keys do not
    collapse into each other (ADR-0025 yearly addendum).
    """
    dates = frozenset({MonthDay(month=12, day=25), MonthDay(month=1, day=1)})
    rule = CalendarRule(hour=9, minute=0, on=YearDays(days=dates))
    item = replace(make_item(_item_id()), rule=rule)
    await store.add(item)
    loaded = await store.get(item.id)
    assert loaded is not None
    assert loaded.rule == rule
    assert loaded.every is None


async def check_edit_replaces_a_calendar_rule_with_an_interval(store: ScheduleStore) -> None:
    """One recurrence shape per item: setting an interval drops the rule in both stores."""
    item = replace(make_item(_item_id()), rule=CalendarRule(hour=9, minute=0))
    await store.add(item)
    assert await store.edit(item.id, ScheduleEdit(every=timedelta(hours=2), set_every=True)) is True
    loaded = await store.get(item.id)
    assert loaded is not None
    assert loaded.every == timedelta(hours=2)
    assert loaded.rule is None


async def check_edit_sets_a_rule_and_moves_the_item_on_the_due_index(
    store: ScheduleStore,
) -> None:
    """Setting a rule re-derives the next fire, so the item moves in the due order too.

    The Redis leg is the one that owes real work here: unlike a text or interval edit, this
    branch has to ``ZADD`` the new due position, so an unmoved index would leave the item
    claimable at its old time (ADR-0025 rule-edit addendum).
    """
    rule = CalendarRule(hour=9, minute=0)
    moved = replace(make_item(_item_id()), due_at=_NOW + timedelta(minutes=5))
    other = replace(make_item(_item_id()), due_at=_NOW + timedelta(hours=1))
    await store.add(moved)
    await store.add(other)
    due_at = _NOW + timedelta(days=3)
    assert (
        await store.edit(moved.id, ScheduleEdit(rule=RuleChange(rule=rule, due_at=due_at))) is True
    )
    loaded = await store.get(moved.id)
    assert loaded is not None
    assert loaded.rule == rule
    assert loaded.due_at == due_at
    # The listing orders by due time, so the retimed item is now the later of the two.
    assert [item.id for item in await store.list_active()] == [other.id, moved.id]
    # And it is no longer claimable at the time it used to be due.
    assert await store.claim_due(_NOW + timedelta(minutes=10), lease=_LEASE, limit=10) == ()


async def check_edit_setting_a_rule_rearms_a_deliverable_reminder(store: ScheduleStore) -> None:
    """A fired one-shot given a rule re-arms PENDING and leaves the deliverable index.

    Left DONE on the due index it would be claimed again and delivered twice, which is why
    this branch borrows ``snooze``'s write set rather than only adding a due entry.
    """
    item = make_item(_item_id())
    await store.add(item)
    (claim,) = await store.claim_due(_NOW, lease=_LEASE, limit=1)
    await store.finish(claim, FireOutcome(fired_at=_NOW, next_due=None, deliverable=True))
    assert [fired.id for fired in await store.deliverable()] == [item.id]
    due_at = _NOW + timedelta(days=1)
    rule = RuleChange(rule=CalendarRule(hour=9, minute=0), due_at=due_at)
    assert await store.edit(item.id, ScheduleEdit(rule=rule)) is True
    assert await store.deliverable() == ()
    loaded = await store.get(item.id)
    assert loaded is not None
    assert loaded.status is ScheduleStatus.PENDING
    assert loaded.due_at == due_at
    # It fires once, at its new time, rather than re-delivering the stale one.
    claims = await store.claim_due(due_at, lease=_LEASE, limit=10)
    assert [claimed.item.id for claimed in claims] == [item.id]


async def check_snooze_refuses_firing_and_unknown(store: ScheduleStore) -> None:
    """A claimed (FIRING) item and an unknown id both answer False, state untouched."""
    assert await store.snooze(_item_id(), until=_NOW + timedelta(minutes=5)) is False
    item = make_item(_item_id())
    await store.add(item)
    (claim,) = await store.claim_due(_NOW, lease=_LEASE, limit=10)
    assert await store.snooze(item.id, until=_NOW + timedelta(minutes=5)) is False
    # The in-flight fire still finishes normally under its token.
    fired = FireOutcome(fired_at=_NOW, next_due=None, deliverable=True)
    assert await store.finish(claim, fired) is True


async def check_snooze_then_cancel_still_sticks(store: ScheduleStore) -> None:
    """The snoozed item stays cancellable; nothing about snooze weakens deletion."""
    item = make_item(_item_id())
    await store.add(item)
    assert await store.snooze(item.id, until=_NOW + timedelta(minutes=30)) is True
    assert await store.cancel(item.id) is True
    assert await store.get(item.id) is None
    assert await store.claim_due(_NOW + timedelta(hours=1), lease=_LEASE, limit=10) == ()


async def check_edit_retexts_a_pending_item(store: ScheduleStore) -> None:
    """edit changes text, leaving the next due time and the recurrence intact."""
    item = make_item(_item_id(), every=timedelta(hours=1))
    await store.add(item)
    assert await store.edit(item.id, ScheduleEdit(text="new text")) is True
    loaded = await store.get(item.id)
    assert loaded is not None
    assert loaded.text == "new text"
    assert loaded.due_at == item.due_at  # the next occurrence is unmoved
    assert loaded.every == timedelta(hours=1)  # recurrence left alone


async def check_edit_sets_and_clears_recurrence(store: ScheduleStore) -> None:
    """set_every replaces the interval; set_every with every=None clears it (a one-shot)."""
    item = make_item(_item_id())
    await store.add(item)
    assert await store.edit(item.id, ScheduleEdit(every=timedelta(hours=2), set_every=True)) is True
    loaded = await store.get(item.id)
    assert loaded is not None
    assert loaded.every == timedelta(hours=2)
    assert loaded.due_at == item.due_at
    assert await store.edit(item.id, ScheduleEdit(every=None, set_every=True)) is True
    loaded = await store.get(item.id)
    assert loaded is not None
    assert loaded.every is None


async def check_edit_taint_is_monotone(store: ScheduleStore) -> None:
    """A tainted edit marks the item; a later clean edit never clears it."""
    item = make_item(_item_id())
    await store.add(item)
    assert await store.edit(item.id, ScheduleEdit(text="a", tainted=True)) is True
    loaded = await store.get(item.id)
    assert loaded is not None
    assert loaded.tainted is True
    assert await store.edit(item.id, ScheduleEdit(text="b", tainted=False)) is True
    loaded = await store.get(item.id)
    assert loaded is not None
    assert loaded.tainted is True  # OR'd forward, never cleared


async def check_edit_refuses_a_firing_item(store: ScheduleStore) -> None:
    """A claimed (FIRING) item cannot be edited; its state is untouched and it still finishes."""
    item = make_item(_item_id())
    await store.add(item)
    (claim,) = await store.claim_due(_NOW, lease=_LEASE, limit=10)
    assert await store.edit(item.id, ScheduleEdit(text="nope")) is False
    loaded = await store.get(item.id)
    assert loaded is not None
    assert loaded.text == "stretch your legs"
    fired = FireOutcome(fired_at=_NOW, next_due=None, deliverable=True)
    assert await store.finish(claim, fired) is True


async def check_edit_unknown_is_false(store: ScheduleStore) -> None:
    """An unknown id answers False, like snooze and cancel."""
    assert await store.edit(_item_id(), ScheduleEdit(text="x")) is False


async def check_edit_rerecur_then_fire_uses_the_new_cadence(store: ScheduleStore) -> None:
    """re-recur leaves the next fire at due_at; the edited interval persists to the re-arm."""
    item = make_item(_item_id(), every=timedelta(hours=1))
    await store.add(item)
    assert await store.edit(item.id, ScheduleEdit(every=timedelta(hours=3), set_every=True)) is True
    (claim,) = await store.claim_due(_NOW, lease=_LEASE, limit=10)  # still due at the old time
    assert claim.item.id == item.id
    rearm_at = _NOW + timedelta(hours=3)
    fired = FireOutcome(fired_at=_NOW, next_due=rearm_at, deliverable=False)
    assert await store.finish(claim, fired) is True
    loaded = await store.get(item.id)
    assert loaded is not None
    assert loaded.every == timedelta(hours=3)
    assert loaded.due_at == rearm_at


ALL_CHECKS = (
    check_missing_get_is_none,
    check_add_get_round_trips,
    check_timezone_fidelity,
    check_list_active_orders_by_due,
    check_cancel_semantics,
    check_claim_due_boundary,
    check_claim_due_limit_and_order,
    check_claimed_item_is_not_reclaimable_within_lease,
    check_lease_expiry_reclaims_with_a_fresh_token,
    check_stale_finish_is_rejected,
    check_finish_rearms_a_recurring_item,
    check_finish_terminal_without_delivery_deletes,
    check_one_shot_reminder_delivery_lifecycle,
    check_recurring_reminder_coalesces_delivery,
    check_fire_taint_ors_onto_the_item,
    check_cancel_sticks_through_an_in_flight_fire,
    check_cancel_clears_a_deliverable_reminder,
    check_release_returns_the_item_to_pending,
    check_claim_orders_across_both_classes,
    check_ack_requires_deliverability,
    check_deliverable_lists_oldest_fired_first,
    check_snooze_moves_a_pending_one_shot,
    check_snooze_rearms_a_deliverable_reminder,
    check_snooze_preserves_a_recurring_grid,
    check_a_calendar_rule_round_trips_and_needs_no_anchor,
    check_a_month_day_rule_round_trips,
    check_a_year_date_rule_round_trips,
    check_edit_replaces_a_calendar_rule_with_an_interval,
    check_edit_sets_a_rule_and_moves_the_item_on_the_due_index,
    check_edit_setting_a_rule_rearms_a_deliverable_reminder,
    check_snooze_refuses_firing_and_unknown,
    check_snooze_then_cancel_still_sticks,
    check_edit_retexts_a_pending_item,
    check_edit_sets_and_clears_recurrence,
    check_edit_taint_is_monotone,
    check_edit_refuses_a_firing_item,
    check_edit_unknown_is_false,
    check_edit_rerecur_then_fire_uses_the_new_cadence,
)
