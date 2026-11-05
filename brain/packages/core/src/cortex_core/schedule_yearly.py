"""Read whether the person named a yearly date, for a schedule call that would repeat it monthly."""

import re

from cortex_core.schedule_tools import SCHEDULE_TOOL_NAME
from cortex_core.tools import ToolCall

YEARLY_DATE_MSG = (
    "REFUSED: the person named a day of a named month and asked for nothing monthly, so this call "
    "with 'on_month_days', which repeats every month, was not run. A date that comes once a year "
    "goes in 'on_dates' as MM-DD with 'at_time', e.g. 'on_dates': ['05-11'] for 11 May."
)

_MONTH = (
    r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?"
    r"|sep(?:t|tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
)
_DAY = r"(?:[1-9]|[12]\d|3[01])(?:st|nd|rd|th)?"
_DAY_OF_MONTH = re.compile(
    rf"\b(?:{_DAY}\s+(?:of\s+)?{_MONTH}|{_MONTH}\.?\s+(?:the\s+)?{_DAY})\b", re.IGNORECASE
)
_MONTHLY = re.compile(r"\bmonth(?:s|ly)?\b", re.IGNORECASE)


def names_yearly_date(message: str) -> bool:
    """Whether ``message`` names a day of a named month and says nothing about months."""
    return _DAY_OF_MONTH.search(message) is not None and _MONTHLY.search(message) is None


def stores_monthly(call: ToolCall) -> bool:
    """Whether ``call`` asks ``schedule_task`` for a rule that repeats on days of every month."""
    return call.name == SCHEDULE_TOOL_NAME and call.arguments.get("on_month_days") is not None


def monthly_for_yearly(call: ToolCall, query: str) -> bool:
    """Whether ``call`` repeats monthly when the person's ``query`` named a yearly date."""
    return stores_monthly(call) and names_yearly_date(query)
