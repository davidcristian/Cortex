"""Argument parsing for the schedule *lifecycle* verbs (ADR-0025): validate, never raise."""

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
from cortex_core.schedule_calendar import next_calendar_due
from cortex_core.schedule_day_args import misplaced_calendar_field, parse_calendar_rule
from cortex_core.schedule_time import UTC_DISPLAY, UTC_ONLY_RESOLVER, DisplayZone, ZoneResolver
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
    """The recurrence change for an edit: ``(set_every, every)`` or a correction string."""
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
    arguments: Mapping[str, Any], now: datetime, zone: DisplayZone, resolve_zone: ZoneResolver
) -> RuleChange | None | str:
    """An edit's calendar rule: a ``RuleChange``, ``None`` when absent, or a correction."""
    if arguments.get("at_time") is None:
        return misplaced_calendar_field(arguments)
    if arguments.get("every_seconds") is not None:
        return _EDIT_EVERY_WITH_AT_TIME
    rule = parse_calendar_rule(arguments, resolve_zone)
    if isinstance(rule, str):
        return rule
    due_at = next_calendar_due(rule, now, zone)
    if due_at is None:
        return UNSCHEDULABLE_RULE
    return RuleChange(rule=rule, due_at=due_at)


def parse_edit(
    arguments: Mapping[str, Any],
    *,
    now: datetime,
    zone: DisplayZone = UTC_DISPLAY,
    resolve_zone: ZoneResolver = UTC_ONLY_RESOLVER,
) -> ScheduleEdit | str:
    """Validate one ``edit_scheduled`` call's changes; return a ScheduleEdit or a correction."""
    text = arguments.get("text")
    if text is not None and (not isinstance(text, str) or not text.strip()):
        return BAD_TEXT
    new_text = text if isinstance(text, str) else None
    rule = _parse_edit_rule(arguments, now, zone, resolve_zone)
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
