"""Close a reply that says something was not stored while a forget of the turn deleted rows."""

import re
from collections.abc import Sequence

from cortex_core.conversation import ToolRun
from cortex_core.forget_claim import deleted_memory

DELETED_UNFOUND_NOTE = (
    "\n\n(A forget call in this turn deleted remembered exchanges, and another call found no "
    "remembered exchange holding its text. What the reply above calls not stored or not found may "
    "be among the deleted exchanges, rather than never stored.)"
)

# "No other records of it remain" says the delete held, unless the clause names finding or storing.
_HELD = (
    r"(?:(?=[^,;:.!?]*\b(?:found|stored|saved|had)\b)|(?![^,;:.!?]*\b(?:remain(?:s|ing)?|left"
    r"|exists?|(?:is|are)\s+kept|any\s*more|any\s+longer|no\s+longer)\b))"
)
_NOT_STORED = re.compile(
    r"\b(?:didn['\u2019]t|did\s+not|couldn['\u2019]t|could\s+not|can['\u2019]t|cannot)\s+"
    r"(?:find|locate|have(?!\s+to\b))\b"
    rf"|\bno\s+(?:other\s+)?(?:records?|memory|entry|entries)\s+of\b{_HELD}"
    r"|\b(?:wasn['\u2019]t|weren['\u2019]t|was\s+not|were\s+not|never\s+(?:been\s+)?)"
    r"\s*(?:stored|saved|remembered|kept|found)\b"
    r"|\bnot\s+(?:stored|saved|found)\b(?!(?:\s+\w+){0,4}\s+(?:any\s*more|any\s+longer)\b)",
    re.IGNORECASE,
)
# "your new phone number wasn't saved" reports a fact of this message, which a forget keeps out.
_NEW = re.compile(r"\bnew\b", re.IGNORECASE)
_CLAUSE_BREAK = re.compile(r"[,;:]")
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+|\n+")


def says_not_stored(reply: str) -> bool:
    """Whether a statement in ``reply`` says something was not found, not stored or not saved."""
    return any(
        not sentence.rstrip().endswith("?")
        and _NEW.search(_CLAUSE_BREAK.split(sentence[: found.start()])[-1]) is None
        for sentence in _SENTENCE_END.split(reply)
        for found in _NOT_STORED.finditer(sentence)
    )


def unfound_claim(runs: Sequence[ToolRun], reply: str, *, unmatched: int) -> bool:
    """Whether a forget among ``runs`` deleted rows, one matched nothing, and ``reply`` says so."""
    return unmatched > 0 and deleted_memory(runs, unmatched) and says_not_stored(reply)
