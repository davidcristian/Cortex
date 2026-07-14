"""Argument parsing for the schedule *lifecycle* verbs (ADR-0025): validate, never raise."""

from collections.abc import Mapping
from datetime import timedelta
from typing import Any

from cortex_core.schedule import ScheduleEdit
from cortex_core.schedule_args import (
    BAD_TEXT,
    MAX_EVERY_SECONDS,
    MIN_EVERY_SECONDS,
    parse_number,
)

_BAD_FOR = f"'for_seconds' must be a number between {MIN_EVERY_SECONDS} and {MAX_EVERY_SECONDS}"
_EDIT_NO_CHANGE = "provide 'text' and/or 'every_seconds' to change something"
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


def parse_edit(arguments: Mapping[str, Any]) -> ScheduleEdit | str:
    """Validate one ``edit_scheduled`` call's changes; return a ScheduleEdit or a correction."""
    text = arguments.get("text")
    if text is not None and (not isinstance(text, str) or not text.strip()):
        return BAD_TEXT
    every = _parse_edit_every(arguments)
    if isinstance(every, str):
        return every
    set_every, interval = every
    new_text = text if isinstance(text, str) else None
    if new_text is None and not set_every:
        return _EDIT_NO_CHANGE
    return ScheduleEdit(text=new_text, every=interval, set_every=set_every)
