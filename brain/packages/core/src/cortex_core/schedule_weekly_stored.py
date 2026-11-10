"""Close a reply over a reminder stored to repeat on chosen weekdays when it names no repeat."""

import re

from cortex_core.schedule_daily import REMINDER_WORD, STORED_ID, names_repeat
from cortex_core.schedule_day_args import SELECTOR_KEYS, parse_on_days
from cortex_core.schedule_tools import DAILY_NOTE, SCHEDULE_TOOL_NAME
from cortex_core.schedule_verbs import CANCEL_SCHEDULED_TOOL_NAME, EDIT_SCHEDULED_TOOL_NAME
from cortex_core.schedule_weekly import WEEKDAY_NAMES
from cortex_core.tools import ToolCall, ToolResult

WEEKLY_STORED_NOTE = (
    "\n\n(A reminder set in this turn repeats every {days}. Ask to make it one time if you meant "
    "only once.)"
)

_DAYS = r"(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday|weekday|weekend)"
_DE = r"(?:montag|dienstag|mittwoch|donnerstag|freitag|samstag|sonntag|werktag)"
_FR = r"(?:lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche|semaine)"
_ES = r"(?:lunes|martes|miércoles|jueves|viernes|sábado|domingo|semana)"
_RO = r"(?:luni|mar[țţ]i|miercuri|joi|vineri|sâmbătă|duminică|săptămână)"
_WEEKLY_WORD = r"(?:weekly|wöchentlich\w*|hebdomadaire\w*|semanal\w*|săptămânal\w*)"
_WEEKLY = (
    re.compile(
        rf"\b(?:every|each)\s+(?:single\s+|other\s+)?(?:week|{_DAYS})s?\b|\b{_DAYS}s\b"
        r"|\bonce\s+a\s+week\b"
        rf"|\bjeden\s+(?:zweiten\s+)?{_DE}\b|\bjede\s+(?:zweite\s+)?Woche\b|\b{_DE}s\b"
        rf"|\bchaque\s+{_FR}\b|\b(?:tous|toutes)\s+les\s+{_FR}s\b"
        rf"|\bcada\s+{_ES}\b|\b(?:todos|todas)\s+l[oa]s\s+{_ES}s?\b|\blos\s+{_ES}s?\b"
        rf"|\bfiecare\s+{_RO}\b",
        re.IGNORECASE,
    ),
    # "Weekly" may describe the reminder's own text ("the weekly report"), as "daily" may.
    re.compile(
        rf"\b{REMINDER_WORD}\S*\s+(?:\S+\s+){{0,2}}{_WEEKLY_WORD}\b"
        rf"|\b{_WEEKLY_WORD}\S*\s+(?:\S+\s+){{0,2}}{REMINDER_WORD}",
        re.IGNORECASE,
    ),
)
# An edit setting any of these gives the item another rule, which its own note names if any.
_RULE_KEYS = frozenset({"at", "at_time", "every_seconds", *SELECTOR_KEYS})
# An edit setting only these keeps the item a rule on chosen weekdays, on the days it names.
_DAY_EDIT_KEYS = frozenset({"id", "at_time", "on_days", "in_zone", "text", "repeat"})


def _days(call: ToolCall, result: ToolResult) -> str:
    """The weekdays a successful ``call`` stored a rule on, short of every day, else empty."""
    if result.is_error or call.name != SCHEDULE_TOOL_NAME or DAILY_NOTE in result.content:
        return ""
    if call.arguments.get("at_time") is None:
        return ""
    return _day_names(call.arguments.get("on_days"))


def _day_names(value: object) -> str:
    """The weekday names an ``on_days`` list holds, short of every day, else empty."""
    days = parse_on_days(value)
    if isinstance(days, str) or len(days) == len(WEEKDAY_NAMES):
        return ""
    names = [WEEKDAY_NAMES[day] for day in sorted(days)]
    return names[0] if len(names) == 1 else f"{', '.join(names[:-1])} and {names[-1]}"


def _moved_days(call: ToolCall) -> str:
    """The new weekday names of an edit that only moves a rule to other weekdays, else empty."""
    keys = {key for key, value in call.arguments.items() if value is not None}
    if call.name != EDIT_SCHEDULED_TOOL_NAME or not keys <= _DAY_EDIT_KEYS:
        return ""
    return _day_names(call.arguments.get("on_days"))


def weekly_after(
    call: ToolCall, result: ToolResult, held: tuple[tuple[str, str], ...]
) -> tuple[tuple[str, str], ...]:
    """The item id and weekdays of each rule on chosen days stored this turn and not ended."""
    if result.is_error:
        return held
    stored = STORED_ID.search(result.content)
    days = _days(call, result)
    if days and stored is not None:
        return (*held, (stored.group(1), days))
    moved = _moved_days(call)
    if moved:
        return tuple((item, moved if item == call.arguments.get("id") else d) for item, d in held)
    ended = call.name == CANCEL_SCHEDULED_TOOL_NAME or (
        call.name == EDIT_SCHEDULED_TOOL_NAME
        and any(call.arguments.get(key) is not None for key in _RULE_KEYS)
    )
    return tuple(each for each in held if not ended or each[0] != call.arguments.get("id"))


def weekly_stored_notes(held: tuple[tuple[str, str], ...], reply: str) -> tuple[str, ...]:
    """One note per distinct weekday set in ``held``, or none when ``reply`` states a repeat."""
    if names_repeat(reply, _WEEKLY, daily=False):
        return ()
    return tuple(WEEKLY_STORED_NOTE.format(days=days) for days in dict.fromkeys(d for _, d in held))
