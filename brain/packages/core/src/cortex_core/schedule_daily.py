"""Close a reply over a reminder stored to repeat every day when the reply names no repeat."""

import re

from cortex_core.schedule_day_args import has_day_selector
from cortex_core.schedule_tools import DAILY_NOTE, SCHEDULE_TOOL_NAME
from cortex_core.schedule_verbs import CANCEL_SCHEDULED_TOOL_NAME, EDIT_SCHEDULED_TOOL_NAME
from cortex_core.tools import ToolCall, ToolResult

DAILY_STORED_NOTE = (
    "\n\n(This reminder repeats every day. Ask to make it one time if you meant only once.)"
)

_STORED_ID = re.compile(r"\bscheduled \w+ (\S+): due ")
_NOT_REPEATED = re.compile(
    r"(?:\bnot|\bnever|n['\u2019]t)\s+(?:be\s+)?repeat\w*|\bwiederholt\s+sich\s+nicht\b"
    r"|\bnicht\s+wiederholt\b|\bne\s+se\s+répète\s+pas\b|\bno\s+se\s+repite\b"
    r"|\bnu\s+se\s+repetă\b",
    re.IGNORECASE,
)
_REPEATS = re.compile(
    r"\b(?:every|each)\s+(?:single\s+)?(?:day|morning|afternoon|evening|night)\b|\bdaily\b"
    r"|\brepeat(?:s|ing)?\b|\brecurring\b"
    r"|\bjeden\s+(?:Tag|Morgen|Nachmittag|Abend)\b|\btäglich\w*|\bwiederholt\b|\bwiederkehrend\w*"
    r"|\btous\s+les\s+(?:jours|matins|après-midi|soirs)\b|\bchaque\s+(?:jour|matin|soir)\b"
    r"|\bquotidien\w*|\bse\s+répète\b|\brécurrent\w*"
    r"|\btodos\s+los\s+días\b|\btodas\s+las\s+(?:mañanas|tardes|noches)\b|\bcada\s+día\b"
    r"|\bdiari(?:o|a|amente)\b|\bse\s+repite\b"
    r"|\bîn\s+fiecare\s+(?:zi|dimineață|seară)\b|\bzilnic\w*|\bse\s+repetă\b",
    re.IGNORECASE,
)


def names_repeat(reply: str) -> bool:
    """Whether ``reply`` says something repeats, in one of the five languages the brain reads."""
    return _REPEATS.search(_NOT_REPEATED.sub(" ", reply)) is not None


def daily_after(call: ToolCall, result: ToolResult, held: tuple[str, ...]) -> tuple[str, ...]:
    """The ids that repeat every day after ``call``: ``held``, plus a daily store, less an end."""
    if result.is_error:
        return held
    stored = _STORED_ID.search(result.content)
    if call.name == SCHEDULE_TOOL_NAME and DAILY_NOTE in result.content and stored is not None:
        return held if stored.group(1) in held else (*held, stored.group(1))
    ended = call.name == CANCEL_SCHEDULED_TOOL_NAME or (
        call.name == EDIT_SCHEDULED_TOOL_NAME
        and (call.arguments.get("every_seconds") is not None or has_day_selector(call.arguments))
    )
    return tuple(each for each in held if not ended or each != call.arguments.get("id"))
