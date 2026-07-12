"""Argument parsing for the ``schedule_task`` built-in (ADR-0025): validate, never raise.

Split from ``schedule_tools.py`` by responsibility (the 300-line cap): this module turns the
model's raw JSON arguments into a typed ``ParsedSchedule`` or a correction message string, following
the volume.py pattern (a str return becomes a trusted ``is_error`` result, so the model can
fix its call). Times are UTC end-to-end in v1: an ``at`` without a UTC offset is rejected
(the spec carries the current UTC time, so the model can always compute one), and the 60 s
recurrence floor is policy here, distinct from the value type's positivity invariant.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from cortex_core.schedule import ScheduleKind

MIN_EVERY_SECONDS = 60
# Ten years: nothing a personal reminder needs recurs slower, and the bound keeps every
# re-arm's datetime arithmetic far from overflow (post-review hardening; next_due is
# additionally total, because an occurrence past datetime.max ends the recurrence).
MAX_EVERY_SECONDS = 315_360_000

_BAD_KIND = '\'kind\' must be "reminder" or "task"'
_TASKS_NOT_WIRED = "this deployment schedules reminders only; 'kind': \"task\" is not available"
_BAD_TEXT = "'text' must be a non-empty string"
_ONE_WHEN = "provide exactly one of 'at' (ISO-8601 with offset) or 'in_seconds'"
_BAD_AT = "'at' must be an ISO-8601 date-time, e.g. 2026-07-12T18:00:00+00:00"
_NAIVE_AT = "'at' must include a UTC offset, e.g. 2026-07-12T18:00:00+00:00"
_BAD_IN_SECONDS = "'in_seconds' must be a positive number of seconds"
_BAD_EVERY = f"'every_seconds' must be a number between {MIN_EVERY_SECONDS} and {MAX_EVERY_SECONDS}"
_BAD_FOR = f"'for_seconds' must be a number between {MIN_EVERY_SECONDS} and {MAX_EVERY_SECONDS}"
_MODEL_NEEDS_TASK = "'model' applies only to 'kind': \"task\""
_BAD_MODEL = "'model' must be a string"


@dataclass(frozen=True, slots=True)
class ParsedSchedule:
    """One validated schedule request: what, when, how often, on which model."""

    kind: ScheduleKind
    text: str
    due_at: datetime
    every: timedelta | None
    model: str


def _parse_kind(arguments: Mapping[str, Any], *, tasks_enabled: bool) -> ScheduleKind | str:
    kind = arguments.get("kind")
    if kind == ScheduleKind.REMINDER.value:
        return ScheduleKind.REMINDER
    if kind == ScheduleKind.TASK.value:
        return ScheduleKind.TASK if tasks_enabled else _TASKS_NOT_WIRED
    return _BAD_KIND


def _parse_number(value: object) -> float | None:
    """A real JSON number, or None (a bool is not a number, since it subclasses int)."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        return float(value)
    except OverflowError:
        # An out-of-double-range int; not a usable quantity (the volume.py guard).
        return None


def _parse_at(at: object) -> datetime | str:
    """An ISO-8601 instant carrying its UTC offset, or a correction string."""
    if not isinstance(at, str):
        return _BAD_AT
    try:
        parsed = datetime.fromisoformat(at)
    except ValueError:
        return _BAD_AT
    if parsed.tzinfo is None or parsed.tzinfo.utcoffset(parsed) is None:
        return _NAIVE_AT
    return parsed


def _delay_from(now: datetime, in_seconds: object) -> datetime | str:
    """``now`` plus a positive number of seconds, or a correction string."""
    delay = _parse_number(in_seconds)
    if delay is None or delay <= 0:
        return _BAD_IN_SECONDS
    try:
        return now + timedelta(seconds=delay)
    except (OverflowError, ValueError):
        # A delay past datetime.max is not a schedulable time.
        return _BAD_IN_SECONDS


def _parse_due_at(arguments: Mapping[str, Any], now: datetime) -> datetime | str:
    """Exactly one of ``at``/``in_seconds``; both are validated, never raising."""
    at = arguments.get("at")
    in_seconds = arguments.get("in_seconds")
    if (at is None) == (in_seconds is None):
        return _ONE_WHEN
    if at is not None:
        return _parse_at(at)
    return _delay_from(now, in_seconds)


def _parse_every(arguments: Mapping[str, Any]) -> timedelta | None | str:
    every_seconds = arguments.get("every_seconds")
    if every_seconds is None:
        return None
    seconds = _parse_number(every_seconds)
    if seconds is None or not MIN_EVERY_SECONDS <= seconds <= MAX_EVERY_SECONDS:
        return _BAD_EVERY
    return timedelta(seconds=seconds)


def _parse_text_and_model(
    arguments: Mapping[str, Any], kind: ScheduleKind
) -> tuple[str, str] | str:
    """The validated ``(text, model)`` pair, or a correction string."""
    text = arguments.get("text")
    if not isinstance(text, str) or not text.strip():
        return _BAD_TEXT
    model = arguments.get("model", "")
    if not isinstance(model, str):
        return _BAD_MODEL
    if model and kind is not ScheduleKind.TASK:
        return _MODEL_NEEDS_TASK
    return text, model


def parse_for_seconds(arguments: Mapping[str, Any]) -> timedelta | str:
    """The validated ``snooze_scheduled`` delay, or a correction string (snooze addendum).

    Snooze is relative by meaning ("from now"), so only ``for_seconds`` exists; its bounds
    mirror the creation policy (the 60 s floor and the ten-year ceiling).
    """
    seconds = _parse_number(arguments.get("for_seconds"))
    if seconds is None or not MIN_EVERY_SECONDS <= seconds <= MAX_EVERY_SECONDS:
        return _BAD_FOR
    return timedelta(seconds=seconds)


def parse_schedule(
    arguments: Mapping[str, Any], *, now: datetime, tasks_enabled: bool
) -> ParsedSchedule | str:
    """Validate one ``schedule_task`` call; return the parsed request or a correction string."""
    kind = _parse_kind(arguments, tasks_enabled=tasks_enabled)
    if isinstance(kind, str):
        return kind
    text_and_model = _parse_text_and_model(arguments, kind)
    if isinstance(text_and_model, str):
        return text_and_model
    due_at = _parse_due_at(arguments, now)
    if isinstance(due_at, str):
        return due_at
    every = _parse_every(arguments)
    if isinstance(every, str):
        return every
    text, model = text_and_model
    return ParsedSchedule(kind=kind, text=text, due_at=due_at, every=every, model=model)
