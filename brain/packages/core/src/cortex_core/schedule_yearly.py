"""Read whether the person named a yearly date, for a schedule call that would repeat it monthly."""

import re

from cortex_core.schedule_day_args import parse_on_month_days
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
_YEARLY_EVENT = re.compile(
    r"\b(?:birthdays?|anniversar(?:y|ies)|renew(?:s|ed|al|als)?|annual(?:ly)?|yearly"
    r"|(?:every|each|once\s+a|per)\s+year)\b",
    re.IGNORECASE,
)
_ORDINAL_DAY = re.compile(r"\b([1-9]|[12]\d|3[01])(?:st|nd|rd|th)\b", re.IGNORECASE)
_ORDINALS = (
    "first",
    "second",
    "third",
    "fourth",
    "fifth",
    "sixth",
    "seventh",
    "eighth",
    "ninth",
    "tenth",
    "eleventh",
    "twelfth",
    "thirteenth",
    "fourteenth",
    "fifteenth",
    "sixteenth",
    "seventeenth",
    "eighteenth",
    "nineteenth",
    "twentieth",
)
_WORD_DAYS = {
    **{word: day for day, word in enumerate(_ORDINALS, start=1)},
    **{f"twenty {word}": 20 + day for day, word in enumerate(_ORDINALS[:9], start=1)},
    "thirtieth": 30,
    "thirty first": 31,
}
_WORD_DAY = "|".join(
    word.replace(" ", r"[\s-]+") for word in sorted(_WORD_DAYS, key=len, reverse=True)
)
_WORD_DAY_OF_MONTH = re.compile(
    rf"\b(?:(?:{_WORD_DAY})\s+(?:of\s+)?{_MONTH}|{_MONTH}\.?\s+(?:the\s+)?(?:{_WORD_DAY}))\b",
    re.IGNORECASE,
)
_WORD_ORDINAL_DAY = re.compile(rf"\b(?:the|every)\s+({_WORD_DAY})\b", re.IGNORECASE)


def names_yearly_date(message: str) -> bool:
    """Whether ``message`` names a yearly event, a day of a named month and nothing about months."""
    return (
        _YEARLY_EVENT.search(message) is not None
        and _DAY_OF_MONTH.search(message) is not None
        and _MONTHLY.search(message) is None
    )


def bare_days(message: str) -> frozenset[int]:
    """The month days ``message`` names as an ordinal, digits or a word, with no month beside it."""
    rest = _WORD_DAY_OF_MONTH.sub(" ", _DAY_OF_MONTH.sub(" ", message))
    digits = {int(match.group(1)) for match in _ORDINAL_DAY.finditer(rest)}
    words = {
        _WORD_DAYS[re.sub(r"[\s-]+", " ", match.group(1).lower())]
        for match in _WORD_ORDINAL_DAY.finditer(rest)
    }
    return frozenset(digits | words)


def stores_monthly(call: ToolCall) -> bool:
    """Whether ``call`` asks ``schedule_task`` for a rule that repeats on days of every month."""
    return call.name == SCHEDULE_TOOL_NAME and call.arguments.get("on_month_days") is not None


def monthly_for_yearly(call: ToolCall, query: str) -> bool:
    """Whether ``call`` repeats monthly on no day the ``query`` names beside a yearly date."""
    if not stores_monthly(call) or not names_yearly_date(query):
        return False
    days = parse_on_month_days(call.arguments.get("on_month_days"))
    return isinstance(days, str) or not days & bare_days(query)


def same_month_days(call: ToolCall, refused: ToolCall) -> bool:
    """Whether ``call`` repeats on the same month days as the ``refused`` call, as a retry does."""
    return call.arguments.get("on_month_days") == refused.arguments.get("on_month_days")
