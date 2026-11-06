"""Read whether a schedule call sets 00:00 as its time of day when the person named no midnight."""

import re

from cortex_core.schedule_tools import SCHEDULE_TOOL_NAME
from cortex_core.schedule_verbs import EDIT_SCHEDULED_TOOL_NAME
from cortex_core.tools import ToolCall

MIDNIGHT_TIME_MSG = (
    "REFUSED: this call sets the time of day to 00:00 and the person named no midnight, so it was "
    "not run. A reminder at 00:00 fires while the person is likely asleep. Call again with the "
    "time of day the person meant, or with the default 09:00 in the schedule zone when they named "
    "none."
)

_SCHEDULING = frozenset({SCHEDULE_TOOL_NAME, EDIT_SCHEDULED_TOOL_NAME})
_MIDNIGHT = re.compile(
    r"\bmidnight\b|\b0?0:00\b(?!\s*[ap]\.?m\b)|\b12(?::00)?\s*a\.?m\b", re.IGNORECASE
)
_AT_TIME = re.compile(r"^\s*0?0:00\s*$")
_AT = re.compile(r"[T ]0?0:00(?::00(?:\.\d+)?)?(?:Z|[+-]\d{2}:?\d{2})?\s*$", re.IGNORECASE)


def names_midnight(message: str) -> bool:
    """Whether ``message`` names midnight as a word, as 0:00 or 00:00, or as 12 am."""
    return _MIDNIGHT.search(message) is not None


def sets_midnight(call: ToolCall) -> bool:
    """Whether ``call`` schedules or edits a reminder whose ``at_time`` or ``at`` time is 00:00."""
    if call.name not in _SCHEDULING:
        return False
    at_time = call.arguments.get("at_time")
    at = call.arguments.get("at")
    return (isinstance(at_time, str) and _AT_TIME.match(at_time) is not None) or (
        isinstance(at, str) and _AT.search(at) is not None
    )


def midnight_unasked(call: ToolCall, query: str) -> bool:
    """Whether ``call`` sets 00:00 as the time of day while the ``query`` names no midnight."""
    return sets_midnight(call) and not names_midnight(query)
