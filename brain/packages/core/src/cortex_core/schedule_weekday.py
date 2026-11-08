"""Read whether a one-time schedule call falls on another weekday than the one the person named."""

import re
from datetime import date, datetime, timedelta

from cortex_core.schedule_tools import SCHEDULE_TOOL_NAME
from cortex_core.schedule_weekly import WEEKDAY_NAMES, named_weekday
from cortex_core.tools import ToolCall

WEEKDAY_DATE_MSG = (
    "REFUSED: the person's message names one weekday, and this call's 'at' falls on another, so "
    "it was not run."
)

# A word that moves the reminder off the named day, or a named date that may decide it instead.
_MOVES_DAY = re.compile(
    r"\b(?:before|beforehand|ahead|advance|after|afterwards?|prior|eve|earlier|previous|following"
    r"|next\s+(?:morning|afternoon|evening)|is\s+over|(?:has|have)\s+passed|tomorrow"
    r"|today|tonight|yesterday|night|midnight|overnight|ago|days?|veille|lendemain|surlendemain"
    r"|avant|après|apres|demain|aujourd|ce\s+soir|nuit|minuit|hier|jours?|(?:matin|soir|soirée)"
    r"\s+suivante?|vorher|davor|danach"
    r"|nach|vor|vortag|vorabend"
    r"|morgen|übermorgen|heute|gestern|nachts?|mitternacht|tage?n?|antes|después|despues"
    r"|víspera|vispera|anterior|siguiente|(?<!la\s)mañana|(?<!la\s)manana|hoy|noche|medianoche"
    r"|ayer|d[íi]as?|înainte|inainte|după|dupa|ajun|mâine|maine|azi|astăzi|astazi|noaptea?"
    r"|miezul|ieri|zi|zile|zilei|january|february|march|april|may|june|july|august|september"
    r"|october|november|december|janvier|février|fevrier|mars|avril|mai|juin|juillet|août|aout"
    r"|septembre|octobre|novembre|décembre|decembre|januar|februar|märz|maerz|juni|juli"
    r"|oktober|dezember|enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|setiembre"
    r"|octubre|noviembre|diciembre|ianuarie|februarie|martie|aprilie|iunie|iulie|septembrie"
    r"|octombrie|noiembrie|decembrie|\d{1,2}(?:st|nd|rd|th)|\d{1,2}[./]\d{1,2}|den\s+\d{1,2})\b",
    re.IGNORECASE,
)
# Before 04:00 or from 22:00 a written date may be read as the night of the day before or after.
_CLEAR_HOURS = range(4, 22)


def _written_at(call: ToolCall) -> datetime | None:
    """The date-time ``call`` writes in a one-time ``at`` at a clear hour, or ``None``."""
    at = call.arguments.get("at")
    if call.name != SCHEDULE_TOOL_NAME or not isinstance(at, str):
        return None
    try:
        when = datetime.fromisoformat(at)
    except ValueError:
        return None
    return when if when.hour in _CLEAR_HOURS else None


def _named(query: str) -> int | None:
    """The one weekday ``query`` names as the reminder's own day, or ``None``."""
    return None if _MOVES_DAY.search(query) is not None else named_weekday(query)


def weekday_mismatch(call: ToolCall, query: str, today: date) -> tuple[date, int] | None:
    """The date ``call`` writes and the weekday ``query`` names, when it is the day after it.

    ``today`` is the date in the person's zone; a date that is today is never read as wrong.
    """
    when = _written_at(call)
    named = _named(query)
    # A date before the named day, or today, may be for a reminder ahead of it, and a date further
    # off is more often another day the person meant.
    if when is None or named is None or when.date() == today or (when.weekday() - named) % 7 != 1:
        return None
    return when.date(), named


def weekday_date_wrong(call: ToolCall, query: str, today: date) -> bool:
    """Whether ``call`` stores a one-time date the day after the weekday ``query`` names."""
    return weekday_mismatch(call, query, today) is not None


def weekday_refusal(day: date, named: int) -> str:
    """The refusal text: the ``named`` weekday, the one ``day`` is, and the dates around it."""
    before = day - timedelta(days=(day.weekday() - named) % 7)
    after = before + timedelta(days=7)
    name, written = WEEKDAY_NAMES[named], WEEKDAY_NAMES[day.weekday()]
    return (
        f"{WEEKDAY_DATE_MSG} The message names {name}; {day.isoformat()} is a "
        f"{written}. The {name}s on either side of it are {before.isoformat()} "
        f"and {after.isoformat()}. Call again with 'at' on the {name} the person meant, keeping "
        "the time of day."
    )
