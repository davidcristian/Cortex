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
_WEEKLY = (
    re.compile(
        rf"\b(?:every|each)\s+(?:single\s+|other\s+)?(?:week|{_DAYS})s?\b|\b{_DAYS}s\b"
        r"|\bonce\s+a\s+week\b",
        re.IGNORECASE,
    ),
    # "Weekly" may describe the reminder's own text ("the weekly report"), as "daily" may.
    re.compile(
        rf"\b{REMINDER_WORD}\S*\s+(?:\S+\s+){{0,2}}weekly\b|\bweekly\S*\s+(?:\S+\s+){{0,2}}"
        rf"{REMINDER_WORD}",
        re.IGNORECASE,
    ),
)
# An edit setting any of these gives the item another rule, which its own note names if any.
_RULE_KEYS = frozenset({"at", "at_time", "every_seconds", *SELECTOR_KEYS})


def _days(call: ToolCall, result: ToolResult) -> str:
    """The weekdays a successful ``call`` stored a rule on, short of every day, else empty."""
    if result.is_error or call.name != SCHEDULE_TOOL_NAME or DAILY_NOTE in result.content:
        return ""
    days = parse_on_days(call.arguments.get("on_days"))
    if isinstance(days, str) or call.arguments.get("at_time") is None:
        return ""
    names = [WEEKDAY_NAMES[day] for day in sorted(days)]
    return names[0] if len(names) == 1 else f"{', '.join(names[:-1])} and {names[-1]}"


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
    ended = call.name == CANCEL_SCHEDULED_TOOL_NAME or (
        call.name == EDIT_SCHEDULED_TOOL_NAME
        and any(call.arguments.get(key) is not None for key in _RULE_KEYS)
    )
    return tuple(each for each in held if not ended or each[0] != call.arguments.get("id"))


def weekly_stored_notes(held: tuple[tuple[str, str], ...], reply: str) -> tuple[str, ...]:
    """One note per distinct weekday set in ``held``, or none when ``reply`` states a repeat."""
    if names_repeat(reply, _WEEKLY):
        return ()
    return tuple(WEEKLY_STORED_NOTE.format(days=days) for days in dict.fromkeys(d for _, d in held))
