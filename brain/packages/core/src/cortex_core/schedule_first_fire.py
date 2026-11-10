"""Read whether a repeat stored this turn first fires before the day the person's message names."""

import re
from datetime import date, datetime, timedelta, tzinfo

from cortex_core.schedule_tools import SCHEDULE_TOOL_NAME
from cortex_core.schedule_weekday import changes_due, item_of
from cortex_core.schedule_weekly import WEEKDAY_NAMES, named_weekday
from cortex_core.tools import ToolCall, ToolResult

FIRST_FIRE_NOTE = (
    "\n\n(A reminder set in this turn first fires {when}, {day} {date} at {time}. Ask to change "
    "its first day if you meant a later one.)"
)

_AFTER_TOMORROW = re.compile(
    r"\b(?:day\s+after\s+tomorrow|apr[eè]s-demain|übermorgen|pasado\s+mañana|poim[âa]ine)\b",
    re.IGNORECASE,
)
_TOMORROW = re.compile(r"\b(?:tomorrow|demain|morgen|mañana|m[âî]ine)\b", re.IGNORECASE)
# "Morgen" and "mañana" also name a morning: "jeden Morgen", "heute Morgen", "por la mañana".
_MORNING = re.compile(
    r"\b(?:jeden|am|den|diesen|heute|guten|la|las|cada|esta|una|toda|todas)\s+(?:morgen|mañana)\b",
    re.IGNORECASE,
)
# An edit of only the repeat interval leaves the next due time alone.
_KEPT_BY_EDIT = frozenset({"id", "text", "repeat", "every_seconds"})
_DUE = re.compile(r"\bdue (\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:[+-]\d{2}:\d{2}|Z)?)")


def days_named(query: str, today: date) -> int:
    """How many days after ``today`` the day ``query`` names is: 1 for tomorrow, else 0 for none.

    The day after tomorrow is 2, and one weekday ``named_weekday`` reads counts to its next date.
    """
    if _AFTER_TOMORROW.search(query) is not None:
        return 2
    if _TOMORROW.search(_MORNING.sub(" ", query)) is not None:
        return 1
    named = named_weekday(query)
    return 0 if named is None else (named - today.weekday()) % 7


def early_first_fire(
    call: ToolCall, result: ToolResult, query: str, now: datetime, tz: tzinfo
) -> tuple[str, str]:
    """The local ``YYYY-MM-DDTHH:MM`` and day word of a repeat ``call`` stored that first fires
    before the day ``query`` names; empty strings when it stored none or fires on that day or later.
    """
    found = _DUE.search(result.content)
    repeat = call.name == SCHEDULE_TOOL_NAME and call.arguments.get("at_time") is not None
    if result.is_error or not repeat or found is None:
        return "", ""
    try:
        first = datetime.fromisoformat(found.group(1))
    except ValueError:
        return "", ""
    first = (first if first.tzinfo is not None else first.replace(tzinfo=tz)).astimezone(tz)
    today = now.astimezone(tz).date()
    ahead = days_named(query, today)
    if not ahead or first.date() >= today + timedelta(days=ahead):
        return "", ""
    days = (first.date() - today).days
    when = "today" if days == 0 else "tomorrow" if days == 1 else f"in {days} days"
    return first.isoformat(timespec="minutes")[:16], when


def early_first_fire_after(
    call: ToolCall,
    result: ToolResult,
    query: str,
    now: datetime,
    tz: tzinfo,
    held: tuple[tuple[str, str, str], ...],
) -> tuple[tuple[str, str, str], ...]:
    """The item id, first fire and day word triples the notes name after ``call``, from ``held``.

    A store first firing early adds its item; a change to an item's due time drops its triple.
    """
    if result.is_error:
        return held
    kept = tuple(each for each in held if not changes_due(call, each[0], _KEPT_BY_EDIT))
    first, when = early_first_fire(call, result, query, now, tz)
    return (*kept, (item_of(call, result), first, when)) if first else kept


def early_first_fire_notes(held: tuple[tuple[str, str, str], ...]) -> tuple[str, ...]:
    """One note per distinct first fire in ``held``, in the order the items were stored."""
    return tuple(
        FIRST_FIRE_NOTE.format(
            when=when,
            day=WEEKDAY_NAMES[date.fromisoformat(first[:10]).weekday()],
            date=first[:10],
            time=first[11:16],
        )
        for first, when in dict.fromkeys((first, when) for _, first, when in held)
    )
