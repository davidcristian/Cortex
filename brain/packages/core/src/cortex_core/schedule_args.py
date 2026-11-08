"""Argument parsing for the ``schedule_task`` built-in: validate, never raise."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any

from cortex_core.schedule import ScheduleKind
from cortex_core.schedule_calendar import CalendarRule, next_calendar_due
from cortex_core.schedule_day_args import misplaced_calendar_field, parse_calendar_rule
from cortex_core.schedule_time import UTC_DISPLAY, UTC_ONLY_RESOLVER, DisplayZone, ZoneResolver

MIN_EVERY_SECONDS = 60
# Ten years: nothing a personal reminder needs recurs slower, and the bound keeps the
# arithmetic for the next occurrence far from datetime overflow.
MAX_EVERY_SECONDS = 315_360_000
# A call that writes the current minute as its 'at' reaches the store a few seconds late.
PAST_MARGIN = timedelta(seconds=60)

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
_BAD_STARTING = "'starting' must be an ISO-8601 calendar date, e.g. 2027-06-15"
_STARTING_NEEDS_AT_TIME = (
    "'starting' sets the first day of an 'at_time' repeat; give 'at_time' too, or put the "
    "first time in 'at' for a fixed interval"
)
_BAD_IN_SECONDS = "'in_seconds' must be a positive number of seconds"
_BAD_EVERY = (
    f"'every_seconds' must be 0 (one-shot) or between {MIN_EVERY_SECONDS} and {MAX_EVERY_SECONDS}"
)
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
    """The validated timing of one request: the first fire, and at most one recurrence shape."""

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
    # An int too large for a float is not a usable quantity.
    except OverflowError:
        return None


def _parse_at(at: object, zone: DisplayZone, now: datetime) -> datetime | str:
    """An ISO-8601 instant, or a correction string; an offset-less one reads as zone-local."""
    if not isinstance(at, str):
        return _BAD_AT
    try:
        parsed = datetime.fromisoformat(at)
    except ValueError:
        return _BAD_AT
    if parsed.tzinfo is None or parsed.tzinfo.utcoffset(parsed) is None:
        return zone.resolve_after(parsed.replace(tzinfo=None), now)
    return parsed


def _past_at(due: datetime, now: datetime, zone: DisplayZone) -> str:
    """The correction for an ``at`` that has already passed, naming the current date-time."""
    return (
        f"'at' {zone.render(due)} has already passed; the current date-time is "
        f"{zone.render(now)} ({zone.name}). Nothing was scheduled. Use a later time, or ask "
        "the user which day they mean."
    )


def _past_starting(start: date, today: date, zone: DisplayZone) -> str:
    """The correction for a ``starting`` day before today, naming today's date."""
    return (
        f"'starting' {start.isoformat()} has already passed; today is {today.isoformat()} "
        f"({zone.name}). Nothing was saved. Use a later date, or ask the user which day "
        "they mean."
    )


def repeat_after(
    raw: object, rule: CalendarRule, now: datetime, zone: DisplayZone
) -> datetime | str:
    """The instant a rule's first occurrence must follow: ``now``, or the start of ``starting``."""
    if raw is None:
        return now
    if not isinstance(raw, str):
        return _BAD_STARTING
    try:
        start = date.fromisoformat(raw)
    except ValueError:
        return _BAD_STARTING
    effective = rule.zone if rule.zone is not None else zone
    today = now.astimezone(effective.tz).date()
    if start < today:
        return _past_starting(start, today, effective)
    if start == today:
        return now
    return effective.resolve(datetime.combine(start, time())) - timedelta(microseconds=1)


def _delay_from(now: datetime, in_seconds: object) -> datetime | str:
    """``now`` plus a positive number of seconds, or a correction string."""
    delay = parse_number(in_seconds)
    if delay is None or delay <= 0:
        return _BAD_IN_SECONDS
    try:
        return now + timedelta(seconds=delay)
    # A delay past datetime.max is not a schedulable time.
    except (OverflowError, ValueError):
        return _BAD_IN_SECONDS


def _parse_due_at(arguments: Mapping[str, Any], now: datetime, zone: DisplayZone) -> datetime | str:
    """Exactly one of ``at``/``in_seconds``; both are validated, never raising."""
    at = arguments.get("at")
    in_seconds = arguments.get("in_seconds")
    if (at is None) == (in_seconds is None):
        return _ONE_WHEN
    if at is None:
        return _delay_from(now, in_seconds)
    return parse_at(at, now, zone)


def parse_at(at: object, now: datetime, zone: DisplayZone) -> datetime | str:
    """A one-time ``at`` that has not passed, or the correction for it."""
    due_at = _parse_at(at, zone, now)
    if isinstance(due_at, datetime) and due_at < now - PAST_MARGIN:
        return _past_at(due_at, now, zone)
    return due_at


def _parse_calendar(
    arguments: Mapping[str, Any], now: datetime, zone: DisplayZone, resolve_zone: ZoneResolver
) -> "_When | str":
    """The ``at_time`` branch: a wall-clock rule, plus the first occurrence it implies."""
    if arguments.get("every_seconds") is not None:
        return _EVERY_WITH_AT_TIME
    rule = parse_calendar_rule(arguments, resolve_zone)
    if isinstance(rule, str):
        return rule
    after = repeat_after(arguments.get("starting"), rule, now, zone)
    if isinstance(after, str):
        return after
    due_at = next_calendar_due(rule, after, zone)
    if due_at is None:
        return UNSCHEDULABLE_RULE
    return _When(due_at=due_at, every=None, rule=rule)


def _misplaced_field(arguments: Mapping[str, Any]) -> str | None:
    """A correction when a field that needs ``at_time`` is given without it, else ``None``."""
    misplaced = misplaced_calendar_field(arguments)
    if misplaced is None and arguments.get("starting") is not None:
        return _STARTING_NEEDS_AT_TIME
    return misplaced


def _parse_when(
    arguments: Mapping[str, Any], now: datetime, zone: DisplayZone, resolve_zone: ZoneResolver
) -> "_When | str":
    """Validate the timing forms jointly: the calendar branch, or the instant-plus-interval one."""
    if arguments.get("at_time") is not None:
        if arguments.get("at") is not None or arguments.get("in_seconds") is not None:
            return _ONE_WHEN
        return _parse_calendar(arguments, now, zone, resolve_zone)
    misplaced = _misplaced_field(arguments)
    if misplaced is not None:
        return misplaced
    due_at = _parse_due_at(arguments, now, zone)
    if isinstance(due_at, str):
        return due_at
    every = _parse_every(arguments)
    if isinstance(every, str):
        return every
    return _When(due_at=due_at, every=every, rule=None)


def starting_property() -> dict[str, dict[str, Any]]:
    """The ``starting`` JSON-schema property of ``schedule_task``."""
    return {
        "starting": {
            "type": "string",
            "description": (
                "The first day an 'at_time' repeat may fire, an ISO-8601 date such as "
                "2027-06-15, for a request like 'starting 15 June'. The first occurrence is the "
                "first day the rule selects on or after it. Omit to start from now. Only with "
                "'at_time'."
            ),
        },
    }


def _parse_every(arguments: Mapping[str, Any]) -> timedelta | None | str:
    every_seconds = arguments.get("every_seconds")
    if every_seconds is None:
        return None
    seconds = parse_number(every_seconds)
    if seconds == 0:
        return None
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
    resolve_zone: ZoneResolver = UTC_ONLY_RESOLVER,
) -> ParsedSchedule | str:
    """Validate one ``schedule_task`` call; return the parsed request or a correction string."""
    kind = _parse_kind(arguments, tasks_enabled=tasks_enabled)
    if isinstance(kind, str):
        return kind
    text_and_model = _parse_text_and_model(arguments, kind)
    if isinstance(text_and_model, str):
        return text_and_model
    when = _parse_when(arguments, now, zone, resolve_zone)
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
