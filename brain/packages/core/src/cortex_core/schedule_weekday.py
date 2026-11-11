"""Read whether a stored one-time reminder falls a day off the one weekday the person named."""

from datetime import date, datetime, tzinfo

from cortex_core.schedule_daily import STORED_ID
from cortex_core.schedule_verbs import (
    CANCEL_SCHEDULED_TOOL_NAME,
    EDIT_SCHEDULED_TOOL_NAME,
    SNOOZE_SCHEDULED_TOOL_NAME,
)
from cortex_core.schedule_weekly import WEEKDAY_NAMES, one_named_weekday, stores_once
from cortex_core.tools import ToolCall, ToolResult

WEEKDAY_OFF_NOTE = (
    "\n\n(A reminder set in this turn is on {day} {date}. Ask to move it if you meant another day.)"
)
WEEKDAY_OFF_NOTES = {
    "fr": "\n\n(Un rappel créé ici est fixé au {day} {date}. Demandez à le déplacer si vous "
    "pensiez à un autre jour.)",
    "de": "\n\n(Eine hier erstellte Erinnerung ist auf {day}, {date} gestellt. Bitten Sie um eine "
    "Verschiebung, wenn Sie einen anderen Tag meinten.)",
    "es": "\n\n(Un recordatorio creado aquí es para el {day} {date}. Pide moverlo si te referías a "
    "otro día.)",
    "ro": "\n\n(Un memento creat aici este pentru {day}, {date}. Cere să fie mutat dacă te gândeai "
    "la altă zi.)",
}
_DAY_NAMES = {
    "fr": ("lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"),
    "de": ("Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"),
    "es": ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"),
    "ro": ("luni", "marți", "miercuri", "joi", "vineri", "sâmbătă", "duminică"),
}


_KEPT_BY_EDIT = frozenset({"id", "text", "repeat"})


def weekday_off(call: ToolCall, result: ToolResult, query: str, tz: tzinfo) -> str:
    """The ISO date a one-time ``call`` stored or moved to a day off the weekday ``query`` names.

    Empty when no one-time item was left on an ``at``, or its date is on the weekday or further.
    """
    at = call.arguments.get("at")
    named = one_named_weekday(query)
    moved = call.name == EDIT_SCHEDULED_TOOL_NAME and not result.is_error
    if not (moved or stores_once(call, result)) or not isinstance(at, str) or named is None:
        return ""
    try:
        when = datetime.fromisoformat(at)
    except ValueError:
        return ""
    if when.tzinfo is not None:
        when = when.astimezone(tz)
    return when.date().isoformat() if (when.weekday() - named) % 7 in {1, 6} else ""


def item_of(call: ToolCall, result: ToolResult) -> str:
    """The id of the item ``call`` moved, or the id its result names as stored, else empty."""
    item = call.arguments.get("id")
    if call.name == EDIT_SCHEDULED_TOOL_NAME and isinstance(item, str):
        return item
    stored = STORED_ID.search(result.content)
    return "" if stored is None else stored.group(1)


def changes_due(call: ToolCall, item_id: str, kept: frozenset[str] = _KEPT_BY_EDIT) -> bool:
    """Whether ``call`` cancels, snoozes or re-times ``item_id``, or any item when that is empty.

    An edit re-times an item when it sets any argument outside ``kept``.
    """
    if item_id and call.arguments.get("id") != item_id:
        return False
    if call.name in {CANCEL_SCHEDULED_TOOL_NAME, SNOOZE_SCHEDULED_TOOL_NAME}:
        return True
    return call.name == EDIT_SCHEDULED_TOOL_NAME and any(
        value is not None for key, value in call.arguments.items() if key not in kept
    )


def weekday_off_after(
    call: ToolCall, result: ToolResult, query: str, tz: tzinfo, held: tuple[tuple[str, str], ...]
) -> tuple[tuple[str, str], ...]:
    """The item id and ISO date pairs the notes name after ``call`` ran, from ``held``.

    A store or move a day off adds its item; a change to an item's due time drops only its pair.
    """
    if result.is_error:
        return held
    kept = tuple(pair for pair in held if not changes_due(call, pair[0]))
    off = weekday_off(call, result, query, tz)
    return (*kept, (item_of(call, result), off)) if off else kept


def weekday_off_dates(held: tuple[tuple[str, str], ...]) -> tuple[str, ...]:
    """The distinct ISO dates of the ``held`` pairs, in the order they were stored."""
    return tuple(dict.fromkeys(stored for _, stored in held))


def weekday_name(day: date, language: str) -> str:
    """The name of the weekday of ``day`` in the note ``language``, else in English."""
    return _DAY_NAMES.get(language, WEEKDAY_NAMES)[day.weekday()]


def weekday_off_note(stored: str, language: str) -> str:
    """The note naming the weekday and date of the ``stored`` ISO date, in ``language``."""
    text = WEEKDAY_OFF_NOTES.get(language, WEEKDAY_OFF_NOTE)
    return text.format(day=weekday_name(date.fromisoformat(stored), language), date=stored)
