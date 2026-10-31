"""Close a reply that says something was noted on a turn whose exchange memory does not store."""

import re
from collections.abc import Sequence

from cortex_core.conversation import ToolRun
from cortex_core.file_request import asks_files
from cortex_core.memory_forget import FORGET_UNTRUSTED_TOOL_NAME
from cortex_core.memory_forget_chosen import FORGET_CHOSEN_TOOL_NAME
from cortex_core.memory_request import asks_kept, asks_not_kept
from cortex_core.turn_context import TurnCapabilities
from cortex_core.untrusted import TaintLedger

UNKEPT_CLAIM_NOTE = (
    "\n\n(Nothing in this message was kept in memory. Send anything you want remembered again in "
    "a message of its own.)"
)

_ADVERB = r"(?:(?:now|just|also|already)\s+)?"
# "As I noted" points back at the reply's own text, not at memory.
_HAVE = rf"(?<!\bas\s)\bI(?:\s+have|['\u2019]ve)?\s+{_ADVERB}"
_WILL = rf"(?<!\bas\s)\bI(?:\s+will|['\u2019]ll)\s+{_ADVERB}"
_NOTED = re.compile(
    rf"{_HAVE}(?:noted|remembered|memori[sz]ed|made\s+a\s+note)\b(?!\s+(?:above|below|earlier))"
    rf"|{_WILL}(?:remember|memori[sz]e|make\s+a\s+note)\b"
    rf"|{_WILL}note\b(?!\s+that\s+(?!(?:down|you|your)\b)\w)",
    re.IGNORECASE,
)
_IN_MEMORY = r"\b(?:in|to|into)\s+(?:my\s+)?(?:mind|memory)\b(?![.\-/\\]\w)"
_PUT = re.compile(
    rf"(?:{_HAVE}(?:saved|stored|kept|recorded|added)|{_WILL}(?:save|store|keep|record|add))\b"
    rf".*{_IN_MEMORY}",
    re.IGNORECASE,
)
# "I read your lease and noted the address." Quoted or reported, "I" is the file's or a person's;
# another subject, or a relative clause, between the verbs makes the later verb theirs.
_THEN = (
    r"(?<![\"\u201c])(?<![\"\u201c:]\s)(?<!\bas\s)(?<!\bsays\s)(?<!\bsaid\s)\bI"
    rf"(?:(?:\s+have|['\u2019]ve)\s+{_ADVERB}(?!(?:not|never)\b)\w+"
    rf"|\s+{_ADVERB}(?:\w+ed|read|found|took|got|saw))\b"
    r"(?:(?!\b(?:you|he|she|they|we|who|which|that|not|never)\b|n['\u2019]t\b)[^:;\"\u201c])*?"
    rf"\band\s+(?:have\s+)?{_ADVERB}"
)
_THEN_NOTED = re.compile(
    rf"{_THEN}(?:noted|remembered|memori[sz]ed|made\s+a\s+note)\b"
    r"(?!\s+(?:nothing|above|below|earlier)\b)"
    rf"|{_THEN}(?:saved|stored|kept|recorded|added)\b.*{_IN_MEMORY}"
    # With no place named, a value was saved; a place or "a copy" names a file.
    rf"|{_THEN}(?:saved|stored|kept|recorded)\b"
    r"(?!\s+(?:a|an|nothing|the\s+(?:file|document))\b)(?![^:]*\b(?:to|in|into|under|on)\s)",
    re.IGNORECASE,
)
_PASSIVE = re.compile(
    r"\b(?:has|have)\s+been\s+(?:noted|remembered)\b(?!\s+(?:by|that)\b)", re.IGNORECASE
)
# A fact is updated to a value; a script is updated to do something, and a reminder is not memory.
_UPDATED = re.compile(
    rf"{_HAVE}updated\s+(?:my\s+(?:records?|notes|memory|memories)\b"
    r"|your\s+(?:records?|information|info|details)\b"
    r"|your\s+(?!(?:[\w'\u2019-]+\s+)*?(?:reminders?|schedule|calendar|alarms?|timers?|events?"
    r"|meetings?|volume|files?|documents?|folders?)\b)"
    r"(?:[\w'\u2019-]+\s+){1,4}?(?:to|as)\s+(?:[\d+\"'\u201c]|(?-i:[A-Z])))"
    r"(?!.*(?:\b(?:not|never|no\s+longer)\b|n['\u2019]t\b|\w\.[a-z]{2,5}\b))",
    re.IGNORECASE,
)
_OPENING = re.compile(r"^\W*(?:got\s+it\W+)?noted\b", re.IGNORECASE)
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+|\n+")


def _states(text: str, patterns: Sequence[re.Pattern[str]]) -> bool:
    """Whether a sentence of ``text`` that asks nothing matches one of ``patterns``."""
    return any(
        not sentence.rstrip().endswith("?")
        and any(pattern.search(sentence) for pattern in patterns)
        for sentence in _SENTENCE_END.split(text)
    )


def claims_kept(reply: str) -> bool:
    """Whether a statement in ``reply`` says something was noted or will be remembered."""
    # A bare "Noted" claims only on the reply's first line; on a later one it is text read back.
    opening = reply.lstrip().partition("\n")[0]
    return _states(reply, (_NOTED, _PUT, _PASSIVE, _UPDATED, _THEN_NOTED)) or _states(
        opening, (_OPENING,)
    )


def _unmatched_keep(taint: TaintLedger, forgets: int, query: str) -> bool:
    """Whether every forget call ran and matched nothing on a message that asks to remember."""
    # A forget request naming a value never stored matches nothing too, so the message decides.
    return 0 < forgets == taint.forget_unmatched == taint.forget_calls and asks_kept(query)


def memory_withheld(
    caps: TurnCapabilities, taint: TaintLedger, runs: Sequence[ToolRun], *, query: str
) -> bool:
    """Whether memory is on and stores nothing of a turn that asked ``query`` and made ``runs``."""
    if caps.memory is None:
        return False
    # A turn that holds a picture (a screen capture, an MCP image or an attachment) is never
    # recorded, whatever the deployment's taint policy says: its reply may transcribe it.
    if taint.opaque:
        return True
    # Recording a tainted turn that forgot the untrusted memories would store a new one.
    if taint.tainted and any(run.ok and run.name == FORGET_UNTRUSTED_TOOL_NAME for run in runs):
        return True
    # A turn that asked to forget a text may name that text in its query or reply.
    forgets = sum(run.name == FORGET_CHOSEN_TOOL_NAME for run in runs)
    if (taint.forget_asked or forgets) and not _unmatched_keep(taint, forgets, query):
        return True
    # The model can answer such a request without the call, and the query names the value.
    if asks_not_kept(query):
        return True
    # An untainted turn read no tool output, so a reply to a file question names folders the
    # model wrote itself.
    return not caps.record_tainted_memory if taint.tainted else asks_files(query)
