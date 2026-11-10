"""Close a reply over a reminder stored while the message asks for one only inside quotes."""

import re
from collections.abc import Sequence

from cortex_core.conversation import ToolRun
from cortex_core.schedule_tools import SCHEDULE_TOOL_NAME

QUOTED_STORED_NOTE = (
    "\n\n({what} was set for you in this turn, and the only words in your message asking for one "
    "stand in quotation marks.)"
)

# An opening mark with no closing mark quotes to the end of the message, and a straight mark
# after a digit is an inch mark, as in 27".
_QUOTED = re.compile(
    r'(?<!\d)"[^"]*(?:"|$)|“[^”]*(?:”|$)|„[^“”]*(?:[“”]|$)'
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
    runs: Sequence[ToolRun], message: str, *, daily: bool, time: str
) -> tuple[str, ...]:
    """The note naming a reminder this turn stored from quoted words only, else none.

    ``daily`` and ``time`` (``HH:MM`` or empty) name the repeat and the time the turn stored.
    """
    stored = any(run.ok and run.name == SCHEDULE_TOOL_NAME for run in runs)
    if not stored or not quoted_request_only(message):
        return ()
    what = f"A{' daily' if daily else ''} reminder{f' at {time}' if time else ''}"
    return (QUOTED_STORED_NOTE.format(what=what),)
