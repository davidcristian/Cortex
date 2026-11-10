"""Close a reply that says something was noted on a turn whose exchange memory does not store."""

import re
from collections.abc import Sequence

from cortex_core.conversation import ToolRun
from cortex_core.file_request import asks_files
from cortex_core.forget_unnamed import row_words
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
    rf"(?:{_HAVE}(?:saved|stored|kept|recorded|added)"
    rf"|{_WILL}(?:make\s+sure\s+to\s+)?(?:save|store|keep|record|add))\b"
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
_VERB = re.compile(
    r"\b(?:not(?:e|ed)|remember(?:ed)?|memori[sz]ed?|sav(?:e|ed)|stor(?:e|ed)|keep|kept"
    r"|record(?:ed)?|add(?:ed)?|updated?)\b",
    re.IGNORECASE,
)
_LABELS = frozenset({"user", "assistant"})
_KEEPING = frozenset({"keep", "kept"})
_OBJECT_END = re.compile(r"[,;:]|\b(?:and|but)\b", re.IGNORECASE)
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+|\n+")
_CLAUSE_END = re.compile(
    r"[,;]\s*(?:(?:and|but|und|aber|et|mais|y|pero|și|şi|dar)\s+)?"
    r"|\s+(?:and|but|und|aber|et|mais|y|pero|și|şi|dar)\s+",
    re.IGNORECASE,
)
# "Remember, don't save this." and "Remember, my code is 4417." name the object in the next clause.
_BARE = re.compile(
    r"\W*(?:(?:please|also|just)\s+)*(?:remember|note|keep\s+in\s+mind|merke?\s+dir"
    r"|merken\s+sie\s+sich|[țţt]ine\s+minte)\W*",
    re.IGNORECASE,
)


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


def _named(text: str) -> set[str]:
    """The words of ``text`` that can name a fact, without a verb of keeping or a speaker label."""
    return {word for word in row_words(text) - _LABELS if not _VERB.fullmatch(word)}


def names_spared(reply: str, spared: Sequence[str]) -> bool:
    """Whether each sentence of ``reply`` claiming a keep says only that a kept row was kept."""
    held = {word for text in spared for word in _named(text)}
    claims = [sentence for sentence in _SENTENCE_END.split(reply) if claims_kept(sentence)]
    objects = [
        (verb.group().lower(), _named(_OBJECT_END.split(sentence[verb.end() :])[0]))
        for sentence in claims
        for verb in _VERB.finditer(sentence)
    ]
    return bool(objects) and all(
        verb in _KEEPING and not held.isdisjoint(words) for verb, words in objects
    )


def unkept_note_due(query: str, reply: str, spared: Sequence[str] = ()) -> bool:
    """Whether a turn that stores nothing shows the note, given what was asked and what it said."""
    # A reply can say the value was updated in words a file edit shares, so a request to keep is
    # enough. A clause that also asks not to keep expects nothing kept, and a question asks none.
    claimed = claims_kept(reply) and not names_spared(reply, spared)
    return claimed or (asks_kept(query) and not asks_not_kept(query)) or _asks_kept_beside(query)


def _asks_kept_beside(query: str) -> bool:
    """Whether a clause of a statement in ``query`` asks to remember and not also not to keep."""
    return any(
        asks_kept(clause) and not asks_not_kept(clause)
        for sentence in _SENTENCE_END.split(query)
        if not sentence.rstrip().endswith("?")
        for clause in _clauses(sentence)
    )


def _clauses(sentence: str) -> list[str]:
    """The clauses of ``sentence``, a request to remember with no object joined to the next one."""
    clauses: list[str] = []
    for clause in _CLAUSE_END.split(sentence):
        if clauses and _BARE.fullmatch(clauses[-1]):
            clauses[-1] = f"{clauses[-1]}, {clause}"
        else:
            clauses.append(clause)
    return clauses


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
