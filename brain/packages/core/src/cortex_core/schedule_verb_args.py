"""Argument parsing for the schedule *lifecycle* verbs (ADR-0025): validate, never raise.

Split from ``schedule_args.py`` at the 300-line cap, along the responsibility line
``schedule_verbs.py`` already draws against ``schedule_tools.py``: creation arguments stay
there, the arguments that change an existing item (``snooze_scheduled``, ``edit_scheduled``)
live here. Same contract as its sibling, so a ``str`` return is a correction the model reads
back as a trusted ``is_error`` result. The shared primitives (the bounds and the JSON-number
guard) are imported from ``schedule_args`` rather than duplicated, a one-way dependency that
keeps one definition of "a legal interval" for creation and edit alike.
"""

from collections.abc import Mapping
from datetime import datetime, timedelta
from typing import Any

from cortex_core.schedule_args import (
    BAD_TEXT,
    MAX_EVERY_SECONDS,
    MIN_EVERY_SECONDS,
    UNSCHEDULABLE_RULE,
    parse_number,
)
from cortex_core.schedule_calendar import CalendarRule, next_calendar_due
from cortex_core.schedule_day_args import (
    DAYS_NEED_AT_TIME,
    has_day_selector,
    parse_at_time,
    parse_day_selector,
)
from cortex_core.schedule_time import UTC_DISPLAY, DisplayZone
from cortex_core.schedule_transitions import RuleChange, ScheduleEdit

_BAD_FOR = f"'for_seconds' must be a number between {MIN_EVERY_SECONDS} and {MAX_EVERY_SECONDS}"
_EDIT_NO_CHANGE = "provide 'text', 'every_seconds', and/or 'at_time' to change something"
_EDIT_EVERY_WITH_AT_TIME = (
    "'at_time' already recurs on the wall clock; drop 'every_seconds', or give 'every_seconds' "
    "on its own to switch this schedule back to a fixed interval"
)
_BAD_EDIT_EVERY = (
    f"'every_seconds' must be 0 (stop repeating) or between {MIN_EVERY_SECONDS} "
    f"and {MAX_EVERY_SECONDS}"
)


def parse_for_seconds(arguments: Mapping[str, Any]) -> timedelta | str:
    """The validated ``snooze_scheduled`` delay, or a correction string (snooze addendum).

    Snooze is relative by meaning ("from now"), so only ``for_seconds`` exists; its bounds
    mirror the creation policy (the 60 s floor and the ten-year ceiling).
    """
    seconds = parse_number(arguments.get("for_seconds"))
    if seconds is None or not MIN_EVERY_SECONDS <= seconds <= MAX_EVERY_SECONDS:
        return _BAD_FOR
    return timedelta(seconds=seconds)


def _parse_edit_every(arguments: Mapping[str, Any]) -> tuple[bool, timedelta | None] | str:
    """The recurrence change for an edit: ``(set_every, every)`` or a correction string.

    ``(False, None)`` when ``every_seconds`` is absent (leave recurrence alone); ``(True, None)``
    on the ``0`` sentinel (stop repeating); ``(True, interval)`` on a bounded interval. The
    tuple return disambiguates the two ``None`` outcomes from a bare error string.
    """
    raw = arguments.get("every_seconds")
    if raw is None:
        return (False, None)
    seconds = parse_number(raw)
    if seconds is None:
        return _BAD_EDIT_EVERY
    if seconds == 0:
        return (True, None)
    if not MIN_EVERY_SECONDS <= seconds <= MAX_EVERY_SECONDS:
        return _BAD_EDIT_EVERY
    return (True, timedelta(seconds=seconds))


def _parse_edit_rule(
    arguments: Mapping[str, Any], now: datetime, zone: DisplayZone
) -> RuleChange | None | str:
    """An edit's calendar rule: a ``RuleChange``, ``None`` when absent, or a correction.

    The rule's next occurrence is derived here rather than asked for, matching creation: the
    model writes the wall time it means and never a due time it would have to keep consistent
    with the recurrence. That derivation is also why the pure ``apply_edit`` can stay clockless
    (ADR-0025 rule-edit addendum). ``every_seconds`` is refused alongside, keeping the item's
    one-recurrence-shape invariant true at the boundary; giving it *alone* still switches a
    calendar item back to an interval, which is what the correction points at.
    """
    if arguments.get("at_time") is None:
        return DAYS_NEED_AT_TIME if has_day_selector(arguments) else None
    if arguments.get("every_seconds") is not None:
        return _EDIT_EVERY_WITH_AT_TIME
    wall = parse_at_time(arguments.get("at_time"))
    if isinstance(wall, str):
        return wall
    on = parse_day_selector(arguments)
    if isinstance(on, str):
        return on
    hour, minute = wall
    rule = CalendarRule(hour=hour, minute=minute, on=on)
    due_at = next_calendar_due(rule, now, zone)
    if due_at is None:
        return UNSCHEDULABLE_RULE
    return RuleChange(rule=rule, due_at=due_at)


def parse_edit(
    arguments: Mapping[str, Any], *, now: datetime, zone: DisplayZone = UTC_DISPLAY
) -> ScheduleEdit | str:
    """Validate one ``edit_scheduled`` call's changes; return a ScheduleEdit or a correction.

    ``text`` (if given) is the new non-empty text; ``every_seconds`` is a new interval, or ``0``
    to stop repeating; ``at_time`` (with an optional ``on_days``) is a wall-clock rule that
    replaces whichever recurrence the item had; omitting a field leaves it. At least one change
    is required. ``tainted`` stays ``False`` here (the verb stamps it from the dispatcher, never
    the model). Setting an interval on a calendar item replaces its rule, which ``apply_edit``
    does: the item holds one recurrence shape, and ``0`` stops whichever it had (ADR-0025
    calendar addendum). The two recurrence forms are mutually exclusive, refused above rather
    than left for ``ScheduleEdit`` to raise on.
    """
    text = arguments.get("text")
    if text is not None and (not isinstance(text, str) or not text.strip()):
        return BAD_TEXT
    new_text = text if isinstance(text, str) else None
    rule = _parse_edit_rule(arguments, now, zone)
    if isinstance(rule, str):
        return rule
    if rule is not None:
        return ScheduleEdit(text=new_text, rule=rule)
    every = _parse_edit_every(arguments)
    if isinstance(every, str):
        return every
    set_every, interval = every
    if new_text is None and not set_every:
        return _EDIT_NO_CHANGE
    return ScheduleEdit(text=new_text, every=interval, set_every=set_every)
