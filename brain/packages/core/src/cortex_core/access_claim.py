"""Close a reply that says it has no access after the turn's file call was refused as unasked."""

import re

from cortex_core.untrusted import TaintLedger

UNSEARCHED_FILES_NOTE = (
    "\n\n(No file was searched in this turn, since the message asked only to remember. Name the "
    "file in a new message to have it read.)"
)

_NO_ACCESS = re.compile(
    r"\b(?:(?:don['\u2019]?t|do\s+not|doesn['\u2019]?t|does\s+not)\s+have\s+(?:any\s+)?access"
    r"|(?:can['\u2019]?t|cannot|can\s+not|unable\s+to|not\s+able\s+to)\s+access"
    r"|no\s+access|inaccessible)\b",
    re.IGNORECASE,
)
_CONDITION = re.compile(r"\b(?:if|once|when|whether|until)\b", re.IGNORECASE)
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+|\n+")


def _says_no_access(sentence: str) -> bool:
    """Whether ``sentence`` states, outside a question or a condition, that it has no access."""
    found = _NO_ACCESS.search(sentence)
    return (
        found is not None
        and not sentence.rstrip().endswith("?")
        and _CONDITION.search(sentence[: found.start()]) is None
    )


def claims_no_access(reply: str) -> bool:
    """Whether a sentence of ``reply`` says it has no access to something."""
    return any(_says_no_access(sentence) for sentence in _SENTENCE_END.split(reply))


def unsearched_files_claim(taint: TaintLedger, reply: str) -> bool:
    """Whether ``reply`` says it has no access on a turn that refused a sidecar call as unasked."""
    return taint.sidecar_refused and claims_no_access(reply)
