"""Read which tools a request to remember did not ask for."""

import re
from collections.abc import Sequence

from cortex_core.memory_request import asks_kept
from cortex_core.schedule_tools import SCHEDULE_TOOL_NAME
from cortex_core.tools import ToolSpec
from cortex_core.volume import SET_VOLUME_TOOL_NAME

_SOUND = re.compile(
    r"\b(?:volume|sound|audio|mute|unmute|muted|louder|quieter|loud|quiet|speakers?"
    r"|turn\s+(?:it|this|that)\s+(?:up|down))\b",
    re.IGNORECASE,
)
_REMINDER = re.compile(
    r"\b(?:remind\w*|alarms?|alerts?|notify|notifications?|schedul\w*|heads[\s-]+up"
    r"|(?:wake|ping|nudge|buzz|text|message|warn|poke)\s+me"
    r"|let\s+me\s+know|tell\s+me\s+(?:when|at|on|before|every|to|in)\b"
    r"|(?:remember|forget)\s+to\s+\w|don['\u2019]?t\s+let\s+me\s+forget)",
    re.IGNORECASE,
)
_ASKED = {SET_VOLUME_TOOL_NAME: _SOUND, SCHEDULE_TOOL_NAME: _REMINDER}
# A question, a second sentence, a path, a link or a named source can need a sidecar tool, while
# a message read wrongly here only keeps its tools offered.
_SOURCE = re.compile(
    r"\?|[.!]\s+\S|/\w|\b\w+\.[a-z]{1,5}\b"
    r"|\b(?:what|which|where|whether|who|how|files?|folders?|director(?:y|ies)|documents?|docs?"
    r"|contents?|pdfs?|photos?|pictures?|images?|attachments?|e-?mails?|mail|inbox|web|websites?"
    r"|wiki|internet|online|pages?|links?|look|find|check|open|fetch|download|browse|show)\b",
    re.IGNORECASE,
)
_WORD = re.compile(r"[a-z]+")


def _asks_a_source(query: str, sidecar: Sequence[ToolSpec]) -> bool:
    """Whether ``query`` holds a named source or a word of a sidecar tool's name."""
    if _SOURCE.search(query.strip()):
        return True
    named = {word for spec in sidecar for word in _WORD.findall(spec.name.lower())}
    return not named.isdisjoint(_WORD.findall(query.lower()))


def unasked_tools(query: str) -> frozenset[str]:
    """The tools left out of a turn whose ``query`` asks to remember and names no use for them."""
    if not asks_kept(query):
        return frozenset()
    return frozenset(name for name, asked in _ASKED.items() if asked.search(query) is None)


def unasked_sidecar_tools(query: str, specs: Sequence[ToolSpec]) -> frozenset[str]:
    """The sidecar tools refused by name on a turn whose ``query`` asks to remember a plain fact."""
    sidecar = [spec for spec in specs if spec.sidecar]
    if not asks_kept(query) or _asks_a_source(query, sidecar):
        return frozenset()
    return frozenset(spec.name for spec in sidecar)
