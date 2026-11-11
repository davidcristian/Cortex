"""Close a reply over a reminder stored while the message asks for one only inside quotes."""

import re
from collections.abc import Sequence

from cortex_core.conversation import ToolRun
from cortex_core.note_language import ENGLISH, in_language
from cortex_core.schedule_tools import SCHEDULE_TOOL_NAME

QUOTED_STORED_NOTE = (
    "\n\n({what} was set for you in this turn, and the only words in your message asking for one "
    "stand in quotation marks.)"
)
QUOTED_STORED_NOTES = {
    "fr": "\n\n({what} a été créé pour vous ici, et les seuls mots de votre message qui en "
    "demandent un sont entre guillemets.)",
    "de": "\n\n({what} wurde hier für Sie erstellt, und die einzigen Wörter Ihrer Nachricht, die "
    "eine verlangen, stehen in Anführungszeichen.)",
    "es": "\n\n(Se creó aquí {what} para ti, y las únicas palabras de tu mensaje que piden uno "
    "están entre comillas.)",
    "ro": "\n\n({what} a fost creat aici pentru tine, iar singurele cuvinte din mesajul tău care "
    "cer unul sunt între ghilimele.)",
}
# The reminder with its repeat and time, the daily word, and the time with its preposition.
_WHAT = {
    ENGLISH: ("A{daily} reminder{at}", " daily", " at {time}"),
    "fr": ("Un rappel{daily}{at}", " quotidien", " à {time}"),
    "de": ("Eine{daily} Erinnerung{at}", " tägliche", " um {time}"),
    "es": ("un recordatorio{daily}{at}", " diario", " a {las} {time}"),
    "ro": ("Un memento{daily}{at}", " zilnic", " la {time}"),
}

# An opening mark with no closing mark quotes to the end of the message, and a straight mark
# after a digit is an inch mark, as in 27", unless a letter follows it.
_QUOTED = re.compile(
    r'(?:(?<!\d)|(?="[^\W\d_]))"[^"]*(?:"|$)|“[^”]*(?:”|$)|„[^“”]*(?:[“”]|$)'
    r"|«[^»]*(?:»|$)|»[^«]*(?:«|$)"
)
_REMIND = (
    r"remind\w*|schedul\w*|alarm\w*|rappel\w*|erinner\w*|recu[eé]rd\w*|recordatori\w*"
    r"|amint\w*|memento\w*"
)
_REMIND_QUOTED = re.compile(rf"\b(?:{_REMIND})", re.IGNORECASE)
# Outside the quotes a request to wake or alert the person is theirs as well.
_ASKS_OUTSIDE = re.compile(
    rf"\b(?:{_REMIND}|wake\s+me|alert\w*|notify\s+me|ping\s+me|weck\w*|réveill\w*"
    r"|despiérta\w*|trez\w*)",
    re.IGNORECASE,
)
_WORD = re.compile(r"[^\W\d_]")


def quoted_request_only(message: str) -> bool:
    """Whether ``message`` asks to remind inside quotation marks and nowhere outside them."""
    quoted = any(_REMIND_QUOTED.search(found.group()) for found in _QUOTED.finditer(message))
    rest = _QUOTED.sub(" ", message)
    # A message that is all quote names no other speaker, so its request is the person's own.
    return quoted and _WORD.search(rest) is not None and _ASKS_OUTSIDE.search(rest) is None


def quoted_stored_notes(
    runs: Sequence[ToolRun], message: str, *, daily: bool, time: str, language: str = ENGLISH
) -> tuple[str, ...]:
    """The note naming a reminder this turn stored from quoted words only, else none.

    ``daily`` and ``time`` (``HH:MM`` or empty) name the repeat and the time the turn stored.
    """
    stored = any(run.ok and run.name == SCHEDULE_TOOL_NAME for run in runs)
    if not stored or not quoted_request_only(message):
        return ()
    shape, daily_word, at = _WHAT.get(language, _WHAT[ENGLISH])
    timed = at.format(time=time, las="la" if time.startswith("01:") else "las") if time else ""
    what = shape.format(daily=daily_word if daily else "", at=timed)
    return (in_language(QUOTED_STORED_NOTE, QUOTED_STORED_NOTES, language).format(what=what),)
