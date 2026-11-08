"""Read whether a schedule call repeats weekly when the person named one weekday and no repeat."""

import re
from datetime import date, datetime, time, timedelta

from cortex_core.schedule_day_args import parse_at_time
from cortex_core.schedule_time import DisplayZone
from cortex_core.schedule_tools import SCHEDULE_TOOL_NAME
from cortex_core.tools import ToolCall

WEEKLY_DAY_MSG = (
    "REFUSED: the person's message names one weekday and no repeat, so this call with 'on_days', "
    "which repeats every week, was not run. For that one day, call again with 'at' set to the "
    "ISO-8601 date-time of its next date and no 'at_time' or 'on_days'."
)

WEEKDAY_NAMES = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
_WEEKDAYS = (
    ("monday", "lundi", "montag", "lunes", "luni"),
    ("tuesday", "mardi", "dienstag", "martes", "marți", "marti", "marţi"),
    ("wednesday", "mercredi", "mittwoch", "miércoles", "miercoles", "miercuri"),
    ("thursday", "jeudi", "donnerstag", "jueves", "joi"),
    ("friday", "vendredi", "freitag", "viernes", "vineri"),
    ("saturday", "samedi", "samstag", "sonnabend", "sábado", "sabado", "sâmbătă", "sambata"),
    ("sunday", "dimanche", "sonntag", "domingo", "duminică", "duminica"),
)
_WEEKDAY = {name: day for day, names in enumerate(_WEEKDAYS) for name in names}
_NAMES = "|".join(sorted(_WEEKDAY, key=len, reverse=True))
_NAMED = re.compile(rf"\b(?:{_NAMES})\b", re.IGNORECASE)
# Any of these may mean the person wants a repeat, so a call beside one is never refused.
_MAY_REPEAT = re.compile(
    r"\b(?:every|each|first|second|third|fourth|fifth|last|premier|dernier|ersten|letzten|primer"
    r"|último|ultimo|prima|ultima|weekly|weeks?|fortnight\w*|biweekly|repeat\w*|recur\w*"
    r"|mornings|afternoons|evenings|nights|forever|indefinitely|permanently|ongoing|going\s+forward"
    r"|sur\s+deux"
    r"|regular\w*|always|usually|routine|until|from\s+now\s+on|again|weekends?|\w+days|move\w*"
    r"|chang\w*|switch\w*|resched\w*|instead|shift\w*|push\w*|later|chaque|tous|toutes|hebdo\w*"
    r"|semaines?|toujours|jusqu\w*|désormais|plutôt|déplac\w*|les\s+(?:lun|mar|mercre|jeu|vendre"
    r"|same|diman)\w*|le\s+(?:lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche)(?!\s*\d)"
    r"|jede[nrs]?|wochen?|wöchentlich\w*|immer|regelmäßig\w*|bis|wieder\w*|\w+tags|statt|anstatt"
    r"|verschieb\w*|änder\w*|todos|todas|cada|semanal\w*|semanas?|siempre|hasta|los\s+(?:lunes"
    r"|martes|mi[ée]rcoles|jueves|viernes|s[áa]bados?|domingos?)|en\s+vez|en\s+lugar|cambi\w*"
    r"|mueve|mover|fiecare|săptămân\w*|saptaman\w*|mereu|întotdeauna|până|pana|lunea|marțea|martea"
    r"|marţea|miercurea|joia|vinerea|sâmbăta|sambata|duminica|mută|muta|schimb\w*|în\s+loc)\b",
    re.IGNORECASE,
)


def named_weekday(message: str) -> int | None:
    """The one weekday ``message`` names, Monday as 0, beside no repeat word; else ``None``."""
    days = {_WEEKDAY[match.group(0).lower()] for match in _NAMED.finditer(message)}
    if len(days) != 1 or _MAY_REPEAT.search(message) is not None:
        return None
    return days.pop()


def names_one_weekday(message: str) -> bool:
    """Whether ``message`` names exactly one weekday and no word that may ask for a repeat."""
    return named_weekday(message) is not None


def weekly_unasked(call: ToolCall, query: str) -> bool:
    """Whether ``call`` stores a weekly rule while the ``query`` names one weekday and no repeat."""
    return (
        call.name == SCHEDULE_TOOL_NAME
        and call.arguments.get("on_days") is not None
        and names_one_weekday(query)
    )


def next_named_date(named: int, at_time: object, now: datetime, zone: DisplayZone) -> date | None:
    """The first ``named`` weekday in ``zone`` whose ``at_time`` is still ahead of ``now``."""
    wall = parse_at_time(at_time)
    if isinstance(wall, str):
        return None
    today = now.astimezone(zone.tz).date()
    ahead = (named - today.weekday()) % 7
    # Today only while an 'at' at that time would still be ahead; once it is reached, a week on.
    if ahead == 0 and zone.resolve_after(datetime.combine(today, time(*wall)), now) <= now:
        ahead = 7
    return today + timedelta(days=ahead)


def weekly_refusal(call: ToolCall, query: str, now: datetime, zone: DisplayZone) -> str:
    """The refusal text, naming the next date of the weekday ``query`` names when it is known."""
    named = named_weekday(query)
    if named is None:
        return WEEKLY_DAY_MSG
    day = next_named_date(named, call.arguments.get("at_time"), now, zone)
    if day is None:
        return WEEKLY_DAY_MSG
    return f"{WEEKLY_DAY_MSG} The next {WEEKDAY_NAMES[named]} is {day.isoformat()}."
