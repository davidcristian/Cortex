"""Read which tools with no card a request to remember did not ask for."""

import re

from cortex_core.memory_request import asks_kept
from cortex_core.schedule_tools import SCHEDULE_TOOL_NAME
from cortex_core.volume import SET_VOLUME_TOOL_NAME

_SOUND = re.compile(
    r"\b(?:volume|sound|audio|mute|unmute|muted|louder|quieter|loud|quiet|speakers?)\b",
    re.IGNORECASE,
)
_REMINDER = re.compile(
    r"\b(?:remind\w*|alarms?|alerts?|notify|notifications?|schedul\w*|wake\s+me|ping\s+me"
    r"|let\s+me\s+know|tell\s+me\s+(?:when|at|on|before|every|to|in)\b"
    r"|(?:remember|forget)\s+to\s+\w|don['\u2019]?t\s+let\s+me\s+forget)",
    re.IGNORECASE,
)
_ASKED = {SET_VOLUME_TOOL_NAME: _SOUND, SCHEDULE_TOOL_NAME: _REMINDER}


def unasked_tools(query: str) -> frozenset[str]:
    """The tools left out of a turn whose ``query`` asks to remember and names no use for them."""
    if not asks_kept(query):
        return frozenset()
    return frozenset(name for name, asked in _ASKED.items() if asked.search(query) is None)
