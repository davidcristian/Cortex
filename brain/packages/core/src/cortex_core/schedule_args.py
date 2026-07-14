"""Argument parsing for the ``schedule_task`` built-in (ADR-0025): validate, never raise.

Split from ``schedule_tools.py`` by responsibility (the 300-line cap): this module turns the
model's raw JSON arguments into a typed ``ParsedSchedule`` or a correction message string, following
the volume.py pattern (a str return becomes a trusted ``is_error`` result, so the model can
fix its call). Storage stays UTC end-to-end; only the *reading* of a wall time is zone-aware
(ADR-0025 display addendum): the spec renders the current time in the configured
``DisplayZone``, so a bare wall time the model writes back means that zone's local time rather
than a rejection. The 60 s recurrence floor is policy here, distinct from the value type's
positivity invariant.

Timing is validated as a whole by ``_parse_when`` rather than field by field, because the
three forms interact: ``at``/``in_seconds`` name an instant and may carry ``every_seconds``,
while ``at_time`` names a *wall clock* rule that carries a day selector and derives its own
first fire (ADR-0025 calendar addendum). That is what keeps the ``ScheduledItem`` invariant, an
interval or a calendar rule and never both, true at the boundary. The rule's own vocabulary
(``at_time`` and the day selectors) is parsed by ``schedule_day_args.py``, shared with the edit
verb; the lifecycle verbs' arguments live in ``schedule_verb_args.py``, which imports the
shared bounds from here.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from cortex_core.schedule import ScheduleKind
from cortex_core.schedule_calendar import CalendarRule, next_calendar_due
from cortex_core.schedule_day_args import (
    DAYS_NEED_AT_TIME,
    has_day_selector,
    parse_at_time,
    parse_day_selector,
)
from cortex_core.schedule_time import UTC_DISPLAY, DisplayZone

MIN_EVERY_SECONDS = 60
# Ten years: nothing a personal reminder needs recurs slower, and the bound keeps every
# re-arm's datetime arithmetic far from overflow (post-review hardening; next_due is
# additionally total, because an occurrence past datetime.max ends the recurrence).
MAX_EVERY_SECONDS = 315_360_000

_BAD_KIND = '\'kind\' must be "reminder" or "task"'
_TASKS_NOT_WIRED = "this deployment schedules reminders only; 'kind': \"task\" is not available"
BAD_TEXT = "'text' must be a non-empty string"
_ONE_WHEN = "provide exactly one of 'at' (ISO-8601), 'in_seconds', or 'at_time' (HH:MM)"
_BAD_AT = "'at' must be an ISO-8601 date-time, e.g. 2026-07-12T18:00:00"
_EVERY_WITH_AT_TIME = (
    "'at_time' already recurs on the wall clock; drop 'every_seconds', or use 'at' with "
    "'every_seconds' for a fixed interval instead"
)
UNSCHEDULABLE_RULE = "'at_time' has no next occurrence that can be scheduled"
_BAD_IN_SECONDS = "'in_seconds' must be a positive number of seconds"
_BAD_EVERY = f"'every_seconds' must be a number between {MIN_EVERY_SECONDS} and {MAX_EVERY_SECONDS}"
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
    rule: CalendarRule | None = None


@dataclass(frozen=True, slots=True)
class _When:
    """The validated timing of one request: the first fire, and at most one recurrence shape.

    The three timing forms (``at``, ``in_seconds``, ``at_time``) and the two recurrence shapes
    are validated together because their legality is joint, not per-field: ``on_days`` means
    nothing without ``at_time``, and ``every_seconds`` contradicts it. One function deciding
    all of it keeps the item invariant (an interval or a rule, never both) true by construction
    rather than re-checked downstream.
    """

    due_at: datetime
    every: timedelta | None
    rule: CalendarRule | None


def _parse_kind(arguments: Mapping[str, Any], *, tasks_enabled: bool) -> ScheduleKind | str:
    kind = arguments.get("kind")
    if kind == ScheduleKind.REMINDER.value:
        return ScheduleKind.REMINDER
    if kind == ScheduleKind.TASK.value:
        return ScheduleKind.TASK if tasks_enabled else _TASKS_NOT_WIRED
    return _BAD_KIND


def parse_number(value: object) -> float | None:
    """A real JSON number, or None (a bool is not a number, since it subclasses int)."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        return float(value)
    except OverflowError:
        # An out-of-double-range int; not a usable quantity (the volume.py guard).
        return None


def _parse_at(at: object, zone: DisplayZone) -> datetime | str:
    """An ISO-8601 instant, or a correction string; an offset-less one reads as zone-local.

    An explicit offset is honored exactly as before, so the model can always be unambiguous.
    A naive value is attached to the display zone (``DisplayZone.resolve`` documents how the
    two DST irregularities settle) rather than rejected, since the zone the model was shown
    the current time in is the only reading a bare wall time can have.
    """
    if not isinstance(at, str):
        return _BAD_AT
    try:
        parsed = datetime.fromisoformat(at)
    except ValueError:
        return _BAD_AT
    if parsed.tzinfo is None or parsed.tzinfo.utcoffset(parsed) is None:
        return zone.resolve(parsed.replace(tzinfo=None))
    return parsed


def _delay_from(now: datetime, in_seconds: object) -> datetime | str:
    """``now`` plus a positive number of seconds, or a correction string."""
    delay = parse_number(in_seconds)
    if delay is None or delay <= 0:
        return _BAD_IN_SECONDS
    try:
        return now + timedelta(seconds=delay)
    except (OverflowError, ValueError):
        # A delay past datetime.max is not a schedulable time.
        return _BAD_IN_SECONDS


def _parse_due_at(arguments: Mapping[str, Any], now: datetime, zone: DisplayZone) -> datetime | str:
    """Exactly one of ``at``/``in_seconds``; both are validated, never raising."""
    at = arguments.get("at")
    in_seconds = arguments.get("in_seconds")
    if (at is None) == (in_seconds is None):
        return _ONE_WHEN
    if at is not None:
        return _parse_at(at, zone)
    return _delay_from(now, in_seconds)


def _parse_calendar(
    arguments: Mapping[str, Any], now: datetime, zone: DisplayZone
) -> "_When | str":
    """The ``at_time`` branch: a wall-clock rule, plus the first occurrence it implies.

    The first fire is derived from the rule rather than asked for separately, so "every
    weekday at 09:00" is one argument the model already knows how to write instead of a due
    time it would have to compute and keep consistent with the recurrence.
    """
    if arguments.get("every_seconds") is not None:
        return _EVERY_WITH_AT_TIME
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
    return _When(due_at=due_at, every=None, rule=rule)


def _parse_when(arguments: Mapping[str, Any], now: datetime, zone: DisplayZone) -> "_When | str":
    """Validate the timing forms jointly: the calendar branch, or the instant-plus-interval one."""
    if arguments.get("at_time") is not None:
        if arguments.get("at") is not None or arguments.get("in_seconds") is not None:
            return _ONE_WHEN
        return _parse_calendar(arguments, now, zone)
    if has_day_selector(arguments):
        return DAYS_NEED_AT_TIME
    due_at = _parse_due_at(arguments, now, zone)
    if isinstance(due_at, str):
        return due_at
    every = _parse_every(arguments)
    if isinstance(every, str):
        return every
    return _When(due_at=due_at, every=every, rule=None)


def _parse_every(arguments: Mapping[str, Any]) -> timedelta | None | str:
    every_seconds = arguments.get("every_seconds")
    if every_seconds is None:
        return None
    seconds = parse_number(every_seconds)
    if seconds is None or not MIN_EVERY_SECONDS <= seconds <= MAX_EVERY_SECONDS:
        return _BAD_EVERY
    return timedelta(seconds=seconds)


def _parse_text_and_model(
    arguments: Mapping[str, Any], kind: ScheduleKind
) -> tuple[str, str] | str:
    """The validated ``(text, model)`` pair, or a correction string."""
    text = arguments.get("text")
    if not isinstance(text, str) or not text.strip():
        return BAD_TEXT
    model = arguments.get("model", "")
    if not isinstance(model, str):
        return _BAD_MODEL
    if model and kind is not ScheduleKind.TASK:
        return _MODEL_NEEDS_TASK
    return text, model


def parse_schedule(
    arguments: Mapping[str, Any],
    *,
    now: datetime,
    tasks_enabled: bool,
    zone: DisplayZone = UTC_DISPLAY,
) -> ParsedSchedule | str:
    """Validate one ``schedule_task`` call; return the parsed request or a correction string."""
    kind = _parse_kind(arguments, tasks_enabled=tasks_enabled)
    if isinstance(kind, str):
        return kind
    text_and_model = _parse_text_and_model(arguments, kind)
    if isinstance(text_and_model, str):
        return text_and_model
    when = _parse_when(arguments, now, zone)
    if isinstance(when, str):
        return when
    text, model = text_and_model
    return ParsedSchedule(
        kind=kind,
        text=text,
        due_at=when.due_at,
        every=when.every,
        model=model,
        rule=when.rule,
    )
