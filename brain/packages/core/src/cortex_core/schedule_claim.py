"""Close a reply that says something was scheduled when no scheduling call in its turn succeeded."""

import re
from collections.abc import Sequence
from itertools import pairwise

from cortex_core.conversation import Message, Role, ToolRun
from cortex_core.memory_claim_update import claims_updated
from cortex_core.note_language import in_language
from cortex_core.schedule_claim_other import claims_scheduled_other
from cortex_core.schedule_tools import LIST_SCHEDULED_TOOL_NAME, SCHEDULE_TOOL_NAME
from cortex_core.schedule_verbs import (
    CANCEL_SCHEDULED_TOOL_NAME,
    EDIT_SCHEDULED_TOOL_NAME,
    SNOOZE_SCHEDULED_TOOL_NAME,
)
from cortex_core.tools import ToolCall

UNSCHEDULED_CLAIM_NOTE = (
    "\n\n(No call in this turn scheduled, edited or snoozed anything. Ask to have your "
    "reminders listed to see what is stored.)"
)
UNSCHEDULED_CLAIM_NOTES = {
    "fr": "\n\n(Aucun appel ici n'a programmé, modifié ou reporté quoi que ce soit. Demandez "
    "la liste de vos rappels pour voir ce qui est enregistré.)",
    "de": "\n\n(Kein Aufruf hier hat etwas geplant, bearbeitet oder verschoben. Bitten Sie um "
    "die Liste Ihrer Erinnerungen, um zu sehen, was gespeichert ist.)",
    "es": "\n\n(Ninguna llamada aquí programó, editó ni pospuso nada. Pide la lista de tus "
    "recordatorios para ver lo que está guardado.)",
    "ro": "\n\n(Niciun apel de aici nu a programat, modificat sau amânat nimic. Cere lista "
    "mementourilor pentru a vedea ce este salvat.)",
}

LISTED_UNCHANGED_NOTE = (
    "\n\n(No call in this turn changed the schedule: the reminders were read as they are stored.)"
)
LISTED_UNCHANGED_NOTES = {
    "fr": "\n\n(Aucun appel ici n'a modifié la programmation : les rappels ont été lus tels "
    "qu'ils sont enregistrés.)",
    "de": "\n\n(Kein Aufruf hier hat die Planung geändert: Die Erinnerungen wurden so gelesen, "
    "wie sie gespeichert sind.)",
    "es": "\n\n(Ninguna llamada aquí cambió la programación: los recordatorios se leyeron tal "
    "como están guardados.)",
    "ro": "\n\n(Niciun apel de aici nu a schimbat programarea: mementourile au fost citite așa "
    "cum sunt salvate.)",
}

MONTHLY_STORED_NOTE = (
    "\n\n(A reminder set in this turn repeats on that day of every month, not once a year. Ask "
    "to change it if you meant once a year.)"
)
MONTHLY_STORED_NOTES = {
    "fr": "\n\n(Un rappel créé ici se répète ce jour-là chaque mois, pas une fois par an. "
    "Demandez à le changer si vous le vouliez une fois par an.)",
    "de": "\n\n(Eine hier erstellte Erinnerung wiederholt sich an diesem Tag jeden Monat, nicht "
    "einmal im Jahr. Bitten Sie darum, sie zu ändern, wenn Sie sie einmal im Jahr wollten.)",
    "es": "\n\n(Un recordatorio creado aquí se repite ese día de cada mes, no una vez al año. "
    "Pide que se cambie si lo querías una vez al año.)",
    "ro": "\n\n(Un memento creat aici se repetă în acea zi a fiecărei luni, nu o dată pe an. "
    "Cere să fie schimbat dacă îl voiai o dată pe an.)",
}

STORED_TIME_NOTE = (
    "\n\n(A reminder set or changed in this turn is at {time}. Ask to change it if you meant "
    "another time of day.)"
)
STORED_TIME_NOTES = {
    "fr": "\n\n(Un rappel créé ou modifié ici est fixé à {time}. Demandez à le modifier si vous "
    "pensiez à une autre heure.)",
    "de": "\n\n(Eine hier erstellte oder geänderte Erinnerung ist auf {time} gestellt. Bitten Sie "
    "um eine Änderung, wenn Sie eine andere Uhrzeit meinten.)",
    "es": "\n\n(Un recordatorio creado o cambiado aquí es a {las} {time}. Pide cambiarlo si te "
    "referías a otra hora del día.)",
    "ro": "\n\n(Un memento creat sau modificat aici este la ora {time}. Cere să fie schimbat dacă "
    "te gândeai la altă oră.)",
}


def stored_time_note(time: str, language: str) -> str:
    """The stored time note naming ``time`` (``HH:MM``), with the Spanish ``la`` for one o'clock."""
    note = in_language(STORED_TIME_NOTE, STORED_TIME_NOTES, language)
    return note.format(time=time, las="la" if time.startswith("01:") else "las")


SCHEDULING_TOOLS = frozenset(
    {SCHEDULE_TOOL_NAME, EDIT_SCHEDULED_TOOL_NAME, SNOOZE_SCHEDULED_TOOL_NAME}
)

_ADVERB = r"(?:(?:now|just|also|successfully)\s+)?"
_FIRST_PERSON = rf"\bI(?:\s+have|['\u2019]ve)?\s+{_ADVERB}"
_PASSIVE = rf"\b(?:has\s+been|have\s+been|is\s+now)\s+{_ADVERB}"
_DONE = rf"(?:{_FIRST_PERSON}|{_PASSIVE})"
_SCHEDULED = re.compile(rf"{_DONE}scheduled\b", re.IGNORECASE)
_SET = re.compile(rf"{_DONE}(?:set|created|added|booked)\b", re.IGNORECASE)
_MOVED = re.compile(rf"{_DONE}moved\b", re.IGNORECASE)
_SCHEDULE_NOUN = re.compile(r"\b(?:reminders?|tasks?|alarms?|schedule)\b", re.IGNORECASE)
# An update of "your alarm code" or "your work schedule" names a fact the person keeps, while
# "your reminder time" names the reminder.
_UPDATED_ITEM = re.compile(
    r"\b(?:reminders?|alarms?)\b(?!\s+(?:codes?|pins?|passcodes?|passwords?|numbers?"
    r"|preferences?|systems?|company)\b)",
    re.IGNORECASE,
)
_PRONOUN = re.compile(r"^\W*(?:it|this|that)\b", re.IGNORECASE)
# "I've moved your 9:00 one to 9:30" moves the reminder a sentence before it names.
_UPDATED_PRONOUN = re.compile(
    r"\b(?:moved|updated|changed|corrected|replaced|amended)\s+"
    r"(?:it|them|(?:(?:your|the)\s+(?:\S+\s+)?)?one)\b",
    re.IGNORECASE,
)
# "I've updated it in memory" names where a fact the person keeps was updated.
_KEPT_PLACE = re.compile(
    r"\b(?:in|to|into)\s+(?:(?:your|my|the)\s+)?(?:\w+\s+){0,2}(?:memory|memories|notes?|file)\b",
    re.IGNORECASE,
)
# "Your 9:00 reminder now goes off at 9:30" gives a new time with no verb of change.
_NOW_FIRES = re.compile(
    r"\bnow\s+(?:go(?:es)?\s+off|fires?|rings?|sounds?)\b|\bis\s+now\s+(?:at|for)\b",
    re.IGNORECASE,
)
_CONDITION = re.compile(r"\b(?:if|unless|once|would|could|can|should)\b", re.IGNORECASE)
_NEGATION = re.compile(r"\b(?:not|never)\b|n['\u2019]t\b", re.IGNORECASE)
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
    r"\s+\**\d{1,2} ?h(?: ?[0-5]\d)?\b(?!\s*de\b)"
    # "réglé pour 2h" may be a duration, so after pour only an hour from 13 or a part of the day.
    r"|\b(?:réglé|programmé|prévu|fixé|enregistré|noté)e?s?\s+pour\s+\**"
    r"(?:(?:1[3-9]|2[0-3]) ?h(?: ?[0-5]\d)?\b(?!\s*de\b)|\d{1,2} ?h ?00\b(?!\s*de\b)"
    r"|\d{1,2} ?h(?: ?[0-5]\d)?\s+(?:du\s+(?:matin|soir)|de\s+l['\u2019]après-midi)\b)"
    # A bare hour up to 12 names no half of the day, as "at 9" does not.
    # Spanish says "a las" before every hour from 2, so "a la 15" names a page or a number.
    r"|\ba\s+las\s+(?:1[3-9]|2[0-3])\b(?![.,]\d)(?=\s*(?:[.,;:!)*]|$|horas?\b|y\s))"
    r"|\ba\s+las?\s+\d{1,2}\s+(?:de\s+la\s+(?:mañana|tarde|noche|madrugada)|del\s+mediod[íi]a)\b"
    r"|\bla\s+ora\s+(?:(?:1[3-9]|2[0-3])\b(?![.,]\d)(?!\s+din\b)"
    r"|\d{1,2}\s+(?:diminea[țţ]a|seara|dup[ăa]-amiaza|noaptea)\b)",
    re.IGNORECASE,
)
# "um 15." names a time only after a word for reminding, since "stieg um 15." names an amount.
_REMIND_UM = re.compile(
    r"\b(?:erinner\w*|weck\w*|alarm\w*)\b[^.!?\n]*?\bum\s+(?:1[3-9]|2[0-3])\b(?![.,]\d)"
    r"(?=\s*(?:[.,;:!)]|$))",
    re.IGNORECASE,
)
# "à 9h de vider" names a time only after a verb of reminding, since "à 2h de route" is a distance.
_REMIND_AT = re.compile(
    r"\brappel(?:le\w*|er|ez|ons)\b[^.!?\n]*?\b(?:à|vers|dès)\s+\**\d{1,2} ?h(?: ?[0-5]\d)?\**"
    r"\s+de\s+(?:\w+(?:er|ir)|prendre|faire|mettre|lire|écrire|dire|rendre|répondre|attendre"
    r"|boire)\b",
    re.IGNORECASE,
)
_DUE = re.compile(r"\bdue \d{4}-\d{2}-\d{2}T(\d{2}:\d{2})")


def _claim(sentence: str, before: str, *, echoed: bool) -> bool:
    """Whether one sentence says something was scheduled, given whether the person said so first."""
    if sentence.rstrip().endswith("?"):
        return False
    named = _names(sentence, before, _SCHEDULE_NOUN)
    # A message drafted in the person's voice repeats their own claim, and names an event rather
    # than the reminder or task a scheduling call makes.
    if _SCHEDULED.search(sentence) and (named or not echoed):
        return True
    if named and _SET.search(sentence) is not None:
        return True
    updated = _MOVED.search(sentence) is not None or claims_updated(sentence)
    named_before = (
        _UPDATED_PRONOUN.search(sentence) is not None
        and _UPDATED_ITEM.search(before) is not None
        and _KEPT_PLACE.search(sentence) is None
    )
    if updated and (named_before or _names(sentence, before, _UPDATED_ITEM)):
        return True
    return _fires_now(sentence, before)


def _fires_now(sentence: str, before: str) -> bool:
    """Whether ``sentence`` states that a named reminder now goes off at a time."""
    found = _NOW_FIRES.search(sentence)
    # A negation after the new time, as in "at 9:30, not 9:00", names the old time.
    return (
        found is not None
        and _TIME_OF_DAY.search(sentence) is not None
        and _CONDITION.search(sentence) is None
        and _NEGATION.search(sentence, 0, found.start()) is None
        and _names(sentence, before, _UPDATED_ITEM)
    )


def _names(sentence: str, before: str, noun: re.Pattern[str]) -> bool:
    """Whether ``sentence`` names ``noun``, or opens with a pronoun after ``before`` names it."""
    # "It is now set to 9:30" names the reminder the sentence ``before`` it names.
    return noun.search(sentence) is not None or (
        _PRONOUN.search(sentence) is not None and noun.search(before) is not None
    )


def claims_scheduled(reply: str, *, said: Sequence[str] = ()) -> bool:
    """Whether a statement in ``reply`` says something was scheduled; a question never does.

    ``said`` are the person's messages in the chat; the last is read before the first sentence.
    """
    echoed = any(claims_scheduled(text) for text in said)
    sentences = (said[-1] if said else "", *_SENTENCE_END.split(reply))
    return any(_claim(sentence, before, echoed=echoed) for before, sentence in pairwise(sentences))


def said_by_person(history: Sequence[Message]) -> tuple[str, ...]:
    """The texts of the person's own messages in ``history``."""
    return tuple(message.text for message in history if message.role is Role.USER)


def unscheduled_claim(runs: Sequence[ToolRun], reply: str, said: Sequence[str] = ()) -> bool:
    """Whether ``reply`` claims a schedule that none of the turn's ``runs`` made."""
    if any(run.ok and run.name in SCHEDULING_TOOLS for run in runs):
        return False
    return claims_scheduled(reply, said=said) or claims_scheduled_other(reply)


def unscheduled_claim_note(runs: Sequence[ToolRun], language: str) -> str:
    """The note for an unscheduled claim; after a list and no cancel it asks for nothing new."""
    done = {run.name for run in runs if run.ok}
    if LIST_SCHEDULED_TOOL_NAME in done and CANCEL_SCHEDULED_TOOL_NAME not in done:
        return in_language(LISTED_UNCHANGED_NOTE, LISTED_UNCHANGED_NOTES, language)
    return in_language(UNSCHEDULED_CLAIM_NOTE, UNSCHEDULED_CLAIM_NOTES, language)


def names_time_of_day(reply: str) -> bool:
    """Whether ``reply`` names a time of day: a clock figure, am or pm, noon or midnight."""
    return any(found.search(reply) is not None for found in (_TIME_OF_DAY, _REMIND_AT, _REMIND_UM))


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
