"""Close a reply that says something was forgotten on a turn whose forget calls deleted nothing."""

import re
from collections.abc import Sequence

from cortex_core.conversation import ToolRun
from cortex_core.memory_forget import FORGET_UNTRUSTED_TOOL_NAME
from cortex_core.memory_forget_chosen import FORGET_CHOSEN_TOOL_NAME

UNFORGOTTEN_CLAIM_NOTE = (
    "\n\n(Nothing was forgotten in this turn: no forget call in it deleted a memory. Ask again to "
    "forget it, in a message of its own.)"
)

_ADVERB = r"(?:(?:now|just|also|already|successfully)\s+)?"
_DONE = (
    rf"(?:\bI(?:\s+have|['\u2019]ve)?\s+{_ADVERB}"
    rf"|\b(?:has\s+been|have\s+been|was|were|is\s+now)\s+{_ADVERB})"
)
_MEMORY = r"\b(?:memor(?:y|ies)|my\s+notes)\b"
_FORGOTTEN = re.compile(rf"{_DONE}forgot(?:ten)?\b(?!\s+to\b)", re.IGNORECASE)
_REMOVED = re.compile(
    rf"{_DONE}(?:removed|deleted|erased|wiped|cleared|purged|discarded|dropped)\b.*{_MEMORY}",
    re.IGNORECASE,
)
_NO_LONGER = re.compile(
    rf"\bno\s+longer\s+(?:remember(?:ed)?\b|(?:in|stored|kept|saved|held)\b.*{_MEMORY})",
    re.IGNORECASE,
)
_UPDATED = re.compile(
    rf"{_DONE}updated\s+(?:my\s+)?(?:memor(?:y|ies)|notes)\b"
    r".*(?:\b(?:not|never|no\s+longer)\b|n['\u2019]t\b)",
    re.IGNORECASE,
)
_NEGATION = re.compile(r"\b(?:no|nothing|none|not|never)\b|n['\u2019]t\b", re.IGNORECASE)
_CLAUSE_BREAK = re.compile(r"[,;:]")
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+|\n+")


def _denied(sentence: str, start: int) -> bool:
    """Whether the clause before ``start`` negates its subject, as "Nothing was removed" does."""
    return _NEGATION.search(_CLAUSE_BREAK.split(sentence[:start])[-1]) is not None


def _claim(sentence: str) -> bool:
    """Whether one sentence that asks nothing says something was removed from memory."""
    if sentence.rstrip().endswith("?"):
        return False
    if _NO_LONGER.search(sentence):
        return True
    for pattern in (_FORGOTTEN, _REMOVED, _UPDATED):
        found = pattern.search(sentence)
        if found is not None and not _denied(sentence, found.start()):
            return True
    return False


def claims_forgotten(reply: str) -> bool:
    """Whether a statement in ``reply`` says something was forgotten or removed from memory."""
    return any(_claim(sentence) for sentence in _SENTENCE_END.split(reply))


def deleted_memory(runs: Sequence[ToolRun], unmatched: int) -> bool:
    """Whether a forget call among ``runs`` deleted a memory.

    ``unmatched`` counts the successful ``forget_memories`` calls that matched nothing.
    """
    if any(run.ok and run.name == FORGET_UNTRUSTED_TOOL_NAME for run in runs):
        return True
    return sum(run.ok and run.name == FORGET_CHOSEN_TOOL_NAME for run in runs) > unmatched


def unforgotten_claim(runs: Sequence[ToolRun], reply: str, *, unmatched: int = 0) -> bool:
    """Whether ``reply`` says something was forgotten that no forget call among ``runs`` deleted."""
    return not deleted_memory(runs, unmatched) and claims_forgotten(reply)
