"""The schedule value invariants + the pure coalescing recurrence math (ADR-0025)."""

from datetime import UTC, datetime, timedelta

import pytest

from cortex_core import (
    FireOutcome,
    ScheduledItem,
    ScheduleEdit,
    ScheduleKind,
    apply_edit,
    next_due,
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
