"""Close a reply that says something was scheduled when no scheduling call in its turn succeeded."""

import re
from collections.abc import Sequence

from cortex_core.conversation import ToolRun
from cortex_core.schedule_tools import SCHEDULE_TOOL_NAME
from cortex_core.schedule_verbs import EDIT_SCHEDULED_TOOL_NAME, SNOOZE_SCHEDULED_TOOL_NAME

UNSCHEDULED_CLAIM_NOTE = (
    "\n\n(Nothing was scheduled in this turn: no scheduling call in it succeeded. Ask again to "
    "schedule it.)"
)

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
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+|\n+")


def claims_scheduled(reply: str) -> bool:
    """Whether a statement in ``reply`` says something was scheduled; a question never does."""
    for sentence in _SENTENCE_END.split(reply):
        if sentence.rstrip().endswith("?"):
            continue
        if _SCHEDULED.search(sentence):
            return True
        if _SET.search(sentence) and _SCHEDULE_NOUN.search(sentence):
            return True
    return False


def unscheduled_claim(runs: Sequence[ToolRun], reply: str) -> bool:
    """Whether ``reply`` claims a schedule that none of the turn's ``runs`` made."""
    if any(run.ok and run.name in SCHEDULING_TOOLS for run in runs):
        return False
    return claims_scheduled(reply)
