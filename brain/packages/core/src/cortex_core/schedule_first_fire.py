"""Read whether a repeat stored or re-timed this turn first fires before the day a message names."""

import re
from datetime import date, datetime, timedelta, tzinfo

from cortex_core.note_language import ENGLISH, in_language
from cortex_core.schedule_tools import SCHEDULE_TOOL_NAME
from cortex_core.schedule_verbs import EDIT_SCHEDULED_TOOL_NAME
from cortex_core.schedule_weekday import changes_due, item_of, weekday_name
from cortex_core.schedule_weekly import one_named_weekday
from cortex_core.tools import ToolCall, ToolResult

FIRST_FIRE_NOTE = (
    "\n\n(A reminder set or changed in this turn first fires {when}, {day} {date} at {time}. Ask "
    "to change its first day if you meant a later one.)"
)
FIRST_FIRE_NOTES = {
    "fr": "\n\n(Un rappel créé ou modifié ici se déclenche pour la première fois {when}, {day} "
    "{date} à {time}. Demandez à modifier son premier jour si vous pensiez à un jour ultérieur.)",
    "de": "\n\n(Eine hier erstellte oder geänderte Erinnerung meldet sich zum ersten Mal {when}, "
    "{day}, {date} um {time}. Bitten Sie um eine Änderung des ersten Tages, wenn Sie einen "
    "späteren meinten.)",
    "es": "\n\n(Un recordatorio creado o cambiado aquí suena por primera vez {when}, el {day} "
    "{date} a {las} {time}. Pide cambiar su primer día si te referías a uno posterior.)",
    "ro": "\n\n(Un memento creat sau modificat aici sună prima dată {when}, {day}, {date} la ora "
    "{time}. Cere să-i fie schimbată prima zi dacă te gândeai la una mai târzie.)",
}
_DAY_WORDS = {
    ENGLISH: ("today", "tomorrow", "in {days} days"),
    "fr": ("aujourd'hui", "demain", "dans {days} jours"),
    "de": ("heute", "morgen", "in {days} Tagen"),
    "es": ("hoy", "mañana", "dentro de {days} días"),
    "ro": ("azi", "mâine", "peste {days} zile"),
}

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

    The day after tomorrow is 2, and the one weekday the message names counts to its next date.
    """
    if _AFTER_TOMORROW.search(query) is not None:
        return 2
    if _TOMORROW.search(_MORNING.sub(" ", query)) is not None:
        return 1
    named = one_named_weekday(query)
    return 0 if named is None else (named - today.weekday()) % 7


def _repeats(call: ToolCall) -> bool:
    """Whether ``call`` stores a repeat at a wall time or edits an item's due time by its rule."""
    if call.name == SCHEDULE_TOOL_NAME:
        return call.arguments.get("at_time") is not None
    moved = call.name == EDIT_SCHEDULED_TOOL_NAME and call.arguments.get("at") is None
    return moved and changes_due(call, "", _KEPT_BY_EDIT)


def early_first_fire(
    call: ToolCall, result: ToolResult, query: str, now: datetime, tz: tzinfo
) -> tuple[str, int]:
    """The local ``YYYY-MM-DDTHH:MM`` and days from today of a repeat ``call`` stored or re-timed
    that first fires before the day ``query`` names; ``("", 0)`` when none or on that day or later.
    """
    found = _DUE.search(result.content)
    if result.is_error or not _repeats(call) or found is None:
        return "", 0
    try:
        first = datetime.fromisoformat(found.group(1))
    except ValueError:
        return "", 0
    first = (first if first.tzinfo is not None else first.replace(tzinfo=tz)).astimezone(tz)
    today = now.astimezone(tz).date()
    ahead = days_named(query, today)
    if not ahead or first.date() >= today + timedelta(days=ahead):
        return "", 0
    return first.isoformat(timespec="minutes")[:16], (first.date() - today).days


def early_first_fire_after(
    call: ToolCall,
    result: ToolResult,
    query: str,
    now: datetime,
    tz: tzinfo,
    held: tuple[tuple[str, str, int], ...],
) -> tuple[tuple[str, str, int], ...]:
    """The item id, first fire and day count triples the notes name after ``call``, from ``held``.

    A store first firing early adds its item; a change to an item's due time drops its triple.
    """
    if result.is_error:
        return held
    kept = tuple(each for each in held if not changes_due(call, each[0], _KEPT_BY_EDIT))
    first, days = early_first_fire(call, result, query, now, tz)
    return (*kept, (item_of(call, result), first, days)) if first else kept


def day_word(days: int, language: str) -> str:
    """The words naming the day ``days`` after today in the note ``language``, else in English."""
    today, tomorrow, later = _DAY_WORDS.get(language, _DAY_WORDS[ENGLISH])
    return today if days == 0 else tomorrow if days == 1 else later.format(days=days)


def early_first_fire_notes(
    held: tuple[tuple[str, str, int], ...], language: str = ENGLISH
) -> tuple[str, ...]:
    """One note per distinct first fire in ``held`` in ``language``, in the order of the stores."""
    note = in_language(FIRST_FIRE_NOTE, FIRST_FIRE_NOTES, language)
    return tuple(
        note.format(
            when=day_word(days, language),
            day=weekday_name(date.fromisoformat(first[:10]), language),
            date=first[:10],
            time=first[11:16],
            las="la" if first[11:13] == "01" else "las",
        )
        for first, days in dict.fromkeys((first, days) for _, first, days in held)
    )
