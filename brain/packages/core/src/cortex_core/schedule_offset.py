"""Read the date a reminder asked for before a yearly date falls on, against a schedule call."""

import re
from datetime import date, datetime, timedelta

from cortex_core.schedule_day_args import parse_on_dates
from cortex_core.schedule_tools import SCHEDULE_TOOL_NAME
from cortex_core.schedule_yearly import names_yearly_date
from cortex_core.tools import ToolCall

OFFSET_DATE_MSG = (
    "REFUSED: the person asked for a reminder a number of days before a yearly date, and this "
    "call's 'on_dates' holds another date, so it was not run."
)

_MONTHS = (
    "jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"
)  # fmt: skip
_MONTH = (
    r"(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?"
    r"|sep(?:t|tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
)
_DAY = r"([1-9]|[12]\d|3[01])(?:st|nd|rd|th)?"
_DAY_OF_MONTH = re.compile(
    rf"\b(?:{_DAY}\s+(?:of\s+)?{_MONTH}|{_MONTH}\.?\s+(?:the\s+)?{_DAY})\b", re.IGNORECASE
)
_COUNTS = {
    "a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
}  # fmt: skip
_BEFORE = re.compile(
    rf"\b(?:the\s+(day)|({'|'.join(_COUNTS)}|\d{{1,2}})\s+(days?|weeks?))\s+before\b",
    re.IGNORECASE,
)
# One leap year and one common year, so a date before 1 March is read in both calendars.
_YEARS = (2001, 2004)


def _named_date(message: str) -> tuple[int, int] | None:
    """The one day of a named month ``message`` names as (month, day), or ``None``."""
    found = _DAY_OF_MONTH.findall(message)
    if len(found) != 1:
        return None
    day1, month1, month2, day2 = found[0]
    month = (month1 or month2).lower()[:3]
    return _MONTHS.index(month) + 1, int(day1 or day2)


def _days_before(message: str) -> int | None:
    """How many days before the named date ``message`` asks for, or ``None`` when it does not."""
    found = _BEFORE.findall(message)
    if len(found) != 1:
        return None
    day, count, unit = found[0]
    if day:
        return 1
    count = count.lower()
    number = _COUNTS[count] if count in _COUNTS else int(count)
    return number * 7 if unit.lower().startswith("week") else number


def wanted_dates(message: str) -> frozenset[str]:
    """The MM-DD a reminder before the yearly date ``message`` names falls on; empty when none."""
    if not names_yearly_date(message):
        return frozenset()
    named = _named_date(message)
    days = _days_before(message)
    if named is None or days is None:
        return frozenset()
    month, day = named
    try:
        dates = [date(year, month, day) - timedelta(days=days) for year in _YEARS]
    except ValueError:
        return frozenset()
    return frozenset(f"{when.month:02d}-{when.day:02d}" for when in dates)


def _stored_dates(call: ToolCall) -> set[str] | None:
    """The MM-DD ``call`` stores in ``on_dates`` or a one-time ``at``, or ``None``."""
    on_dates = call.arguments.get("on_dates")
    if on_dates is not None:
        stored = parse_on_dates(on_dates)
        if isinstance(stored, str):
            return None
        return {f"{md.month:02d}-{md.day:02d}" for md in stored}
    at = call.arguments.get("at")
    if not isinstance(at, str):
        return None
    try:
        once = datetime.fromisoformat(at)
    except ValueError:
        return None
    return {f"{once.month:02d}-{once.day:02d}"}


def offset_date_wrong(call: ToolCall, query: str) -> bool:
    """Whether ``call`` stores a date other than the one the ``query`` wants before its date."""
    if call.name != SCHEDULE_TOOL_NAME:
        return False
    stored = _stored_dates(call)
    if stored is None:
        return False
    wanted = wanted_dates(query)
    return bool(wanted) and not stored <= wanted


def offset_refusal(query: str) -> str:
    """The refusal text for a wrong date, naming the date the ``query`` asks the reminder for."""
    wanted = " or ".join(f"'{when}'" for when in sorted(wanted_dates(query)))
    return (
        f"{OFFSET_DATE_MSG} Counted from the named date, the reminder falls on {wanted}. Call "
        f"again with that date in 'on_dates' and the same 'at_time'."
    )
