"""Read whether a stored one-time reminder falls a day off the one weekday the person named."""

from datetime import date, datetime, tzinfo

from cortex_core.schedule_weekly import WEEKDAY_NAMES, named_weekday, stores_once
from cortex_core.tools import ToolCall, ToolResult

WEEKDAY_OFF_NOTE = (
    "\n\n(The reminder set in this turn is on {day} {date}. Ask to move it if you meant another "
    "day.)"
)
WEEKDAY_OFF_NOTES = {
    "fr": "\n\n(Le rappel créé ici est fixé au {day} {date}. Demandez à le déplacer si vous "
    "pensiez à un autre jour.)",
    "de": "\n\n(Die hier erstellte Erinnerung ist auf {day}, {date} gestellt. Bitten Sie um eine "
    "Verschiebung, wenn Sie einen anderen Tag meinten.)",
    "es": "\n\n(El recordatorio creado aquí es para el {day} {date}. Pide moverlo si te referías a "
    "otro día.)",
    "ro": "\n\n(Mementoul creat aici este pentru {day}, {date}. Cere să fie mutat dacă te gândeai "
    "la altă zi.)",
}
_DAY_NAMES = {
    "fr": ("lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"),
    "de": ("Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"),
    "es": ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"),
    "ro": ("luni", "marți", "miercuri", "joi", "vineri", "sâmbătă", "duminică"),
}


def weekday_off(call: ToolCall, result: ToolResult, query: str, tz: tzinfo) -> str:
    """The ISO date a one-time ``call`` stored a day before or after the weekday ``query`` names.

    Empty when the call stored nothing one time, or its date is on that weekday or further off.
    """
    at = call.arguments.get("at")
    named = named_weekday(query)
    if not stores_once(call, result) or not isinstance(at, str) or named is None:
        return ""
    try:
        when = datetime.fromisoformat(at)
    except ValueError:
        return ""
    if when.tzinfo is not None:
        when = when.astimezone(tz)
    return when.date().isoformat() if (when.weekday() - named) % 7 in {1, 6} else ""


def weekday_off_note(stored: str, language: str) -> str:
    """The note naming the weekday and date of the ``stored`` ISO date, in ``language``."""
    day = date.fromisoformat(stored)
    names = _DAY_NAMES.get(language, WEEKDAY_NAMES)
    text = WEEKDAY_OFF_NOTES.get(language, WEEKDAY_OFF_NOTE)
    return text.format(day=names[day.weekday()], date=stored)
