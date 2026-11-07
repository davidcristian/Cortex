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
_REPEATS = re.compile(
    r"\b(?:every|each)\s+(?:single\s+)?(?:day|morning|afternoon|evening|night)\b|\bdaily\b"
    r"|\brepeat(?:s|ing)\b|\brecurring\b"
    r"|\bjeden\s+(?:Tag|Morgen|Nachmittag|Abend)\b|\btäglich\w*|\bwiederholt\b|\bwiederkehrend\w*"
    r"|\btous\s+les\s+(?:jours|matins|après-midi|soirs)\b|\bchaque\s+(?:jour|matin|soir)\b"
    r"|\bquotidien\w*|\bse\s+répète\b|\brécurrent\w*"
    r"|\btodos\s+los\s+días\b|\btodas\s+las\s+(?:mañanas|tardes|noches)\b"
    r"|\bcada\s+(?:día|mañana|tarde|noche)\b|\bdiari(?:o|a|amente)\b|\bse\s+repite\b"
    r"|\bîn\s+fiecare\s+(?:zi|dimineață|seară)\b|\bzi\s+de\s+zi\b|\bzilnic\w*|\bse\s+repetă\b",
    re.IGNORECASE,
)
# A condition or an offer anywhere in a sentence makes its repeat a choice rather than the fact.
_CHOICE = re.compile(
    r"\b(?:if|unless|whether|can|could|would|should|shall|may|might|want\w*|wish\w*|like"
    r"|prefer\w*|rather|instead|si|s['\u2019]il|peux|peut|pouvez|pourr\w*|veux|veut|voulez"
    r"|voudr\w*|souhait\w*|aimer\w*|préfér\w*|plutôt|wenn|falls|ob|kann|kannst|können|könnt\w*"
    r"|soll\w*|willst|wollen|wollt\w*|möcht\w*|wünsch\w*|lieber|statt|anstatt|puedo|puede"
    r"|puedes|podr\w*|quier\w*|dese\w*|gustar\w*|dacă|daca|pot|poți|poate|puteți|putea|vrei"
    r"|vreți|vrea|dorești|doriți|dori)\b",
    re.IGNORECASE,
)
_NEGATION = re.compile(
    r"\b(?:not|never|no|ne|pas|jamais|nicht|nie|kein\w*|nunca|jamás|nu|nici\w*)\b"
    r"|n['\u2019]t\b|\bn['\u2019]",
    re.IGNORECASE,
)
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+|\n+")
_CLAUSE_END = re.compile(r"[,;]")


def _states_repeat(sentence: str) -> bool:
    """Whether ``sentence`` states a repeat, rather than asking, offering or negating one."""
    if "?" in sentence or _CHOICE.search(sentence) is not None:
        return False
    return any(
        _NEGATION.search(clause) is None and _REPEATS.search(clause) is not None
        for clause in _CLAUSE_END.split(sentence)
    )


def names_repeat(reply: str) -> bool:
    """Whether a statement in ``reply`` says something repeats, in one of five languages."""
    return any(_states_repeat(sentence) for sentence in _SENTENCE_END.split(reply))


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
