"""The schedule value invariants + the pure coalescing recurrence math (ADR-0025)."""

from datetime import UTC, datetime, timedelta

import pytest

from cortex_core import (
    UTC_DISPLAY,
    CalendarRule,
    FireOutcome,
    RuleChange,
    ScheduledItem,
    ScheduleEdit,
    ScheduleKind,
    ScheduleStatus,
    apply_edit,
    apply_snooze,
    next_due,
    next_occurrence,
    recurrence_base,
)

_NOW = datetime(2026, 7, 12, 12, 0, 0, tzinfo=UTC)
_NAIVE = datetime(2026, 7, 12, 12, 0, 0)  # noqa: DTZ001 - the invalid input under test


def _item(**overrides: object) -> ScheduledItem:
    fields: dict[str, object] = {
        "id": "s1",
        "kind": ScheduleKind.REMINDER,
        "text": "stretch",
        "session_id": "",
        "due_at": _NOW,
        "created_at": _NOW,
    }
    fields.update(overrides)
    return ScheduledItem(**fields)  # pyright: ignore[reportArgumentType] - kwargs built per test


def test_item_requires_aware_due_at() -> None:
    with pytest.raises(ValueError, match="due_at must be timezone-aware"):
        _item(due_at=_NAIVE)


def test_item_requires_aware_created_at() -> None:
    with pytest.raises(ValueError, match="created_at must be timezone-aware"):
        _item(created_at=_NAIVE)


def test_item_requires_aware_deliverable_since() -> None:
    with pytest.raises(ValueError, match="deliverable_since must be timezone-aware"):
        _item(deliverable_since=_NAIVE)


def test_item_requires_aware_anchor() -> None:
    with pytest.raises(ValueError, match="anchor must be timezone-aware"):
        _item(every=timedelta(hours=1), anchor=_NAIVE)


@pytest.mark.parametrize("every", [timedelta(0), timedelta(seconds=-60)])
def test_item_requires_a_positive_every(every: timedelta) -> None:
    with pytest.raises(ValueError, match="positive interval"):
        _item(every=every)


def test_item_accepts_aware_fields_and_recurrence() -> None:
    item = _item(every=timedelta(minutes=1), deliverable_since=_NOW)
    assert item.every == timedelta(minutes=1)
    assert item.deliverable_since == _NOW


@pytest.mark.parametrize("every", [timedelta(0), timedelta(seconds=-60)])
def test_edit_requires_a_positive_every(every: timedelta) -> None:
    with pytest.raises(ValueError, match="positive interval"):
        ScheduleEdit(every=every, set_every=True)


def test_apply_edit_keeps_timing_and_ors_taint() -> None:
    """The pure edit: new text/recurrence, ``due_at`` kept, taint OR'd never cleared."""
    item = _item(due_at=_NOW, every=timedelta(hours=1), tainted=True)
    edited = apply_edit(
        item, ScheduleEdit(text="new", every=timedelta(hours=2), set_every=True, tainted=False)
    )
    assert edited.text == "new"
    assert edited.every == timedelta(hours=2)
    assert edited.due_at == _NOW  # the next occurrence never moves
    assert edited.tainted is True  # already tainted, a clean edit cannot clear it


def test_apply_edit_leaves_unset_fields_and_can_clear_recurrence() -> None:
    item = _item(text="keep", every=timedelta(hours=1))
    unchanged = apply_edit(item, ScheduleEdit(tainted=True))
    assert unchanged.text == "keep"  # text=None leaves it
    assert unchanged.every == timedelta(hours=1)  # set_every=False leaves it
    assert unchanged.tainted is True  # a tainted edit still marks it
    cleared = apply_edit(item, ScheduleEdit(set_every=True))
    assert cleared.every is None  # set_every with every=None makes it a one-shot


def test_rule_change_requires_an_aware_due_at() -> None:
    with pytest.raises(ValueError, match=r"RuleChange\.due_at must be timezone-aware"):
        RuleChange(rule=CalendarRule(hour=9, minute=0), due_at=_NAIVE)


def test_edit_refuses_a_rule_and_an_interval_change_together() -> None:
    """The item's one-shape invariant, kept true at the boundary rather than in apply_edit."""
    change = RuleChange(rule=CalendarRule(hour=9, minute=0), due_at=_NOW)
    with pytest.raises(ValueError, match="an interval change or a calendar rule, never both"):
        ScheduleEdit(rule=change, every=timedelta(hours=1), set_every=True)


def test_apply_edit_setting_a_rule_moves_the_due_time_and_drops_the_interval() -> None:
    """A rule is its own grid, so the next fire is re-derived rather than left where it was."""
    due = _NOW + timedelta(days=1)
    item = _item(due_at=_NOW, every=timedelta(hours=1), anchor=_NOW - timedelta(hours=5))
    rule = CalendarRule(hour=9, minute=0, days=frozenset({0, 4}))
    edited = apply_edit(item, ScheduleEdit(rule=RuleChange(rule=rule, due_at=due)))
    assert edited.rule == rule
    assert edited.due_at == due  # unlike an interval re-recur, the timing moves
    assert edited.every is None  # the item carries one recurrence shape
    assert edited.anchor is None  # an interval grid origin a rule has no use for


def test_apply_edit_setting_a_rule_rearms_a_fired_reminder_off_the_deliverable_index() -> None:
    """The ``apply_snooze`` precedent: a DONE item must never reach the due index still DONE.

    Were it left DONE, the claim path's staleness re-check (which only guards PENDING) would
    let the terminal record fire a second time.
    """
    item = _item(due_at=_NOW, status=ScheduleStatus.DONE, deliverable_since=_NOW)
    due = _NOW + timedelta(days=1)
    edited = apply_edit(
        item, ScheduleEdit(rule=RuleChange(rule=CalendarRule(hour=9, minute=0), due_at=due))
    )
    assert edited.status is ScheduleStatus.PENDING
    assert edited.deliverable_since is None


def test_apply_edit_setting_a_rule_still_retexts_and_ors_taint() -> None:
    item = _item(text="keep", tainted=False)
    change = RuleChange(rule=CalendarRule(hour=7, minute=30), due_at=_NOW + timedelta(days=1))
    assert apply_edit(item, ScheduleEdit(rule=change)).text == "keep"
    retexted = apply_edit(item, ScheduleEdit(text="new", rule=change, tainted=True))
    assert retexted.text == "new"
    assert retexted.tainted is True


def test_apply_snooze_rearms_a_delivered_one_shot_without_an_anchor() -> None:
    """A one-shot has no recurrence grid: snooze re-arms it PENDING and leaves anchor unset."""
    item = _item(due_at=_NOW, status=ScheduleStatus.DONE, deliverable_since=_NOW)
    until = _NOW + timedelta(minutes=15)
    snoozed = apply_snooze(item, until)
    assert snoozed.status is ScheduleStatus.PENDING
    assert snoozed.due_at == until
    assert snoozed.deliverable_since is None
    assert snoozed.anchor is None


def test_apply_snooze_pins_a_recurring_grid_to_the_pre_snooze_due() -> None:
    item = _item(due_at=_NOW, every=timedelta(hours=1))
    snoozed = apply_snooze(item, _NOW + timedelta(minutes=20))
    assert snoozed.anchor == _NOW  # the original occurrence becomes the grid origin
    assert snoozed.due_at == _NOW + timedelta(minutes=20)  # only the next fire moves


def test_apply_snooze_keeps_an_existing_anchor_on_a_second_snooze() -> None:
    origin = _NOW - timedelta(hours=2)
    item = _item(due_at=_NOW, every=timedelta(hours=1), anchor=origin)
    snoozed = apply_snooze(item, _NOW + timedelta(minutes=5))
    assert snoozed.anchor == origin  # a re-snooze never re-pins the grid


def test_recurrence_base_prefers_the_anchor_then_falls_back_to_due_at() -> None:
    origin = _NOW - timedelta(hours=3)
    anchored = _item(due_at=_NOW, every=timedelta(hours=1), anchor=origin)
    assert recurrence_base(anchored) == origin
    assert recurrence_base(_item(due_at=_NOW)) == _NOW


def test_fire_outcome_requires_aware_fired_at() -> None:
    with pytest.raises(ValueError, match="fired_at must be timezone-aware"):
        FireOutcome(fired_at=_NAIVE, next_due=None, deliverable=False)


def test_fire_outcome_requires_aware_next_due() -> None:
    with pytest.raises(ValueError, match="next_due must be timezone-aware"):
        FireOutcome(fired_at=_NOW, next_due=_NAIVE, deliverable=False)


def test_next_due_is_none_for_a_one_shot() -> None:
    assert next_due(_NOW, None, _NOW) is None


def test_next_due_rejects_a_non_positive_interval() -> None:
    with pytest.raises(ValueError, match="positive 'every' interval"):
        next_due(_NOW, timedelta(0), _NOW)


def test_next_due_before_the_anchor_is_one_interval_after_it() -> None:
    # The pure function is total: a due time still in the future advances one interval.
    got = next_due(_NOW + timedelta(hours=1), timedelta(hours=2), _NOW)
    assert got == _NOW + timedelta(hours=3)


def test_next_due_fired_exactly_on_time_advances_one_interval() -> None:
    assert next_due(_NOW, timedelta(hours=1), _NOW) == _NOW + timedelta(hours=1)


def test_next_due_coalesces_missed_occurrences() -> None:
    # Down for 3.5 intervals: the next re-arm is the single first occurrence in the future.
    got = next_due(_NOW - timedelta(hours=3, minutes=30), timedelta(hours=1), _NOW)
    assert got == _NOW + timedelta(minutes=30)


def test_next_due_on_an_exact_interval_boundary_is_strictly_after_now() -> None:
    got = next_due(_NOW - timedelta(hours=2), timedelta(hours=1), _NOW)
    assert got == _NOW + timedelta(hours=1)


def test_next_due_past_datetime_max_ends_the_recurrence() -> None:
    # Terminal beats a fire that can never persist its re-arm and lease-cycles forever.
    near_max = datetime(9999, 12, 31, tzinfo=UTC)
    assert next_due(near_max, timedelta(days=365), near_max) is None


def test_an_item_takes_an_interval_or_a_calendar_rule_but_never_both() -> None:
    """The invariant that lets ``next_occurrence`` answer without reconciling a conflict."""
    with pytest.raises(ValueError, match="never both"):
        _item(every=timedelta(hours=1), rule=CalendarRule(hour=9, minute=0))


def test_an_item_accepts_either_recurrence_shape_alone() -> None:
    assert _item(every=timedelta(hours=1)).rule is None
    assert _item(rule=CalendarRule(hour=9, minute=0)).every is None


def test_next_occurrence_reads_the_rule_for_a_calendar_item() -> None:
    """A calendar item re-arms off its wall clock, ignoring ``due_at`` entirely."""
    item = _item(rule=CalendarRule(hour=9, minute=0))
    assert next_occurrence(item, _NOW, UTC_DISPLAY) == datetime(2026, 7, 13, 9, 0, tzinfo=UTC)


def test_next_occurrence_keeps_the_anchored_interval_arithmetic() -> None:
    """An interval item's path is unchanged, snooze grid included."""
    item = _item(every=timedelta(hours=1), anchor=_NOW - timedelta(minutes=30))
    assert next_occurrence(item, _NOW, UTC_DISPLAY) == _NOW + timedelta(minutes=30)


def test_next_occurrence_is_terminal_for_a_one_shot() -> None:
    assert next_occurrence(_item(), _NOW, UTC_DISPLAY) is None


def test_a_snoozed_calendar_item_gets_no_anchor_and_returns_to_its_rule() -> None:
    """The rule IS the grid, so the series recovers without the interval anchor machinery."""
    item = _item(rule=CalendarRule(hour=9, minute=0))
    snoozed = apply_snooze(item, _NOW + timedelta(minutes=15))
    assert snoozed.anchor is None
    fired_at = _NOW + timedelta(minutes=15)
    assert next_occurrence(snoozed, fired_at, UTC_DISPLAY) == datetime(
        2026, 7, 13, 9, 0, tzinfo=UTC
    )


def test_setting_an_interval_clears_a_calendar_rule() -> None:
    """One recurrence shape: an edit that sets ``every`` replaces the rule rather than colliding."""
    item = _item(rule=CalendarRule(hour=9, minute=0))
    edited = apply_edit(item, ScheduleEdit(every=timedelta(hours=2), set_every=True))
    assert edited.every == timedelta(hours=2)
    assert edited.rule is None


def test_the_stop_repeating_sentinel_clears_a_calendar_rule_too() -> None:
    item = _item(rule=CalendarRule(hour=9, minute=0))
    edited = apply_edit(item, ScheduleEdit(every=None, set_every=True))
    assert edited.every is None
    assert edited.rule is None


def test_a_retext_leaves_a_calendar_rule_alone() -> None:
    item = _item(rule=CalendarRule(hour=9, minute=0))
    assert apply_edit(item, ScheduleEdit(text="new")).rule == CalendarRule(hour=9, minute=0)
