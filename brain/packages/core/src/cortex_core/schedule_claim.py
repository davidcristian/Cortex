"""Close a reply that says something was scheduled when no scheduling call in its turn succeeded."""

import re
from collections.abc import Sequence

from cortex_core.conversation import Message, Role, ToolRun
from cortex_core.schedule_tools import SCHEDULE_TOOL_NAME
from cortex_core.schedule_verbs import EDIT_SCHEDULED_TOOL_NAME, SNOOZE_SCHEDULED_TOOL_NAME
from cortex_core.tools import ToolCall

UNSCHEDULED_CLAIM_NOTE = (
    "\n\n(Nothing was scheduled in this turn: no scheduling call in it succeeded. Ask again to "
    "schedule it.)"
)

MONTHLY_STORED_NOTE = (
    "\n\n(The reminder set in this turn repeats on that day of every month, not once a year. Ask "
    "to change it if you meant once a year.)"
)

STORED_TIME_NOTE = (
    "\n\n(The reminder set or changed in this turn is at {time}. Ask to change it if you meant "
    "another time of day.)"
)
STORED_TIME_NOTES = {
    "fr": "\n\n(Le rappel créé ou modifié ici est fixé à {time}. Demandez à le modifier si vous "
    "pensiez à une autre heure.)",
    "de": "\n\n(Die hier erstellte oder geänderte Erinnerung ist auf {time} gestellt. Bitten Sie "
    "um eine Änderung, wenn Sie eine andere Uhrzeit meinten.)",
    "es": "\n\n(El recordatorio creado o cambiado aquí es a las {time}. Pide cambiarlo si te "
    "referías a otra hora del día.)",
    "ro": "\n\n(Mementoul creat sau modificat aici este la ora {time}. Cere să fie schimbat dacă "
    "te gândeai la altă oră.)",
}

SCHEDULING_TOOLS = frozenset(
    {SCHEDULE_TOOL_NAME, EDIT_SCHEDULED_TOOL_NAME, SNOOZE_SCHEDULED_TOOL_NAME}
)

_ADVERB = r"(?:(?:now|just|also|successfully)\s+)?"
_FIRST_PERSON = rf"\bI(?:\s+have|['\u2019]ve)?\s+{_ADVERB}"
_PASSIVE = rf"\b(?:has\s+been|have\s+been|is\s+now)\s+{_ADVERB}"
_DONE = rf"(?:{_FIRST_PERSON}|{_PASSIVE})"
_SCHEDULED = re.compile(rf"{_DONE}scheduled\b", re.IGNORECASE)
_SET = re.compile(rf"{_DONE}(?:set|created|added|booked)\b", re.IGNORECASE)
_SCHEDULE_NOUN = re.compile(r"\b(?:reminders?|tasks?|alarms?|schedule)\b", re.IGNORECASE)
_YEARLY = re.compile(
    r"\b(?:every|each|per|once\s+a)\s+year\b|\b(?:yearly|annual(?:ly)?)\b", re.IGNORECASE
)
_MONTHLY = re.compile(r"\bmonth(?:s|ly)?\b", re.IGNORECASE)
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+|\n+")
_TIME_OF_DAY = re.compile(
    r"\b\d{1,2}(?::\d{2})?\s*[ap]\.?m\.?(?![a-z])|\b\d{1,2}:\d{2}\b|\bnoon\b|\bmidnight\b"
    r"|\b\d{1,2}(?:[.:]\d{2})? ?Uhr\b"
    # An hour written with h only after a word for a point in time, since "dure 2h30" is a duration.
    r"|\b(?:à|vers|dès|(?:demain|aujourd['\u2019]hui),?|um|gegen|a\s+las|at)"
    r"\s+\d{1,2} ?h(?: ?[0-5]\d)?\b(?!\s*de\b)"
    # "réglé pour 2h" may be a duration, so after pour only an hour from 13 or a part of the day.
    r"|\b(?:réglé|programmé|prévu|fixé|enregistré|noté)e?s?\s+pour\s+"
    r"(?:(?:1[3-9]|2[0-3]) ?h(?: ?[0-5]\d)?\b(?!\s*de\b)"
    r"|\d{1,2} ?h(?: ?[0-5]\d)?\s+(?:du\s+(?:matin|soir)|de\s+l['\u2019]après-midi)\b)",
    re.IGNORECASE,
)
_DUE = re.compile(r"\bdue \d{4}-\d{2}-\d{2}T(\d{2}:\d{2})")


def _claim(sentence: str, *, echoed: bool) -> bool:
    """Whether one sentence says something was scheduled, given whether the person said so first."""
    if sentence.rstrip().endswith("?"):
        return False
    named = _SCHEDULE_NOUN.search(sentence) is not None
    # A message drafted in the person's voice repeats their own claim, and names an event rather
    # than the reminder or task a scheduling call makes.
    if _SCHEDULED.search(sentence) and (named or not echoed):
        return True
    return named and _SET.search(sentence) is not None


def claims_scheduled(reply: str, *, said: Sequence[str] = ()) -> bool:
    """Whether a statement in ``reply`` says something was scheduled; a question never does.

    ``said`` are the person's own messages in the chat.
    """
    echoed = any(claims_scheduled(text) for text in said)
    return any(_claim(sentence, echoed=echoed) for sentence in _SENTENCE_END.split(reply))


def said_by_person(history: Sequence[Message]) -> tuple[str, ...]:
    """The texts of the person's own messages in ``history``."""
    return tuple(message.text for message in history if message.role is Role.USER)


def unscheduled_claim(runs: Sequence[ToolRun], reply: str, said: Sequence[str] = ()) -> bool:
    """Whether ``reply`` claims a schedule that none of the turn's ``runs`` made."""
    if any(run.ok and run.name in SCHEDULING_TOOLS for run in runs):
        return False
    return claims_scheduled(reply, said=said)


def names_time_of_day(reply: str) -> bool:
    """Whether ``reply`` names a time of day: a clock figure, am or pm, noon or midnight."""
    return _TIME_OF_DAY.search(reply) is not None


def stored_time(call: ToolCall, result: str) -> str:
    """The HH:MM a timed schedule or edit ``call`` stored, read from its ``result``; else empty."""
    timed = call.name == EDIT_SCHEDULED_TOOL_NAME or (
        call.name == SCHEDULE_TOOL_NAME
        and (call.arguments.get("at") is not None or call.arguments.get("at_time") is not None)
    )
    found = _DUE.search(result) if timed else None
    return "" if found is None else found.group(1)


def claims_yearly(reply: str) -> bool:
    """Whether ``reply`` says a reminder repeats yearly and says nothing about months."""
    return _YEARLY.search(reply) is not None and _MONTHLY.search(reply) is None
