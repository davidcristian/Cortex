"""Find the sentence of a reply that says a row the turn's forget calls kept was forgotten."""

import re
from collections.abc import Iterable, Sequence

from cortex_core.conversation import ToolRun
from cortex_core.forget_forms import AND, FORMS
from cortex_core.forget_unnamed import row_words
from cortex_core.memory_forget import FORGET_UNTRUSTED_TOOL_NAME
from cortex_core.memory_values import digit_runs
from cortex_core.note_language import ENGLISH, in_language
from cortex_core.untrusted import TaintLedger

KEPT_CLAIM_NOTE = (
    '\n\n(The sentence "{sentence}" is wrong about at least one of these: all are still in '
    "memory, since your message was not read as meaning them:"
)
KEPT_CLAIM_NOTES = {
    "fr": "\n\n(La phrase « {sentence} » est fausse pour au moins l'un de ceux-ci : tous sont "
    "toujours en mémoire, car votre message n'a pas été lu comme les visant :",
    "de": "\n\n(Der Satz „{sentence}“ trifft auf mindestens einen von diesen nicht zu: alle sind "
    "noch gespeichert, weil Ihre Nachricht nicht als auf sie bezogen gelesen wurde:",
    "es": "\n\n(La frase «{sentence}» es falsa para al menos uno de estos: todos siguen en "
    "memoria, porque tu mensaje no se leyó como referido a ellos:",
    "ro": "\n\n(Propoziția „{sentence}” este greșită pentru cel puțin unul dintre acestea: toate "
    "sunt încă în memorie, pentru că mesajul tău nu a fost citit ca referindu-se la ele:",
}

_ACTIVE = r"\bI(?:\s+have|['\u2019]ve)?"
_PASSIVE = r"(?:\b(?:has|have)\s+(?:already\s+)?been|\bwas|\bwere|\bis\s+now)"
_ADVERB = r"\s+(?:(?:now|just|also|already|successfully)\s+)?"
_VERB = r"(?:forgot(?:ten)?|removed|deleted|erased|wiped|cleared|purged|discarded|dropped)\b"
_UPDATE = (
    r"updated\s+(?:my|your)\s+(?:memor(?:y|ies)|records|notes)\s+to\s+"
    r"(?:remove|delete|erase|forget)\b"
)
# A removal's object follows an active or update form and comes before a passive verb.
_GONE = re.compile(
    rf"(?P<after>{_ACTIVE}{_ADVERB}(?:{_VERB}|{_UPDATE})|{_PASSIVE}{_ADVERB}{_UPDATE})"
    rf"|{_PASSIVE}{_ADVERB}{_VERB}",
    re.IGNORECASE,
)
_JOIN = re.compile(
    r"[\"\u201c\u201d\u201e\u2018\u00ab\u00bb]"
    r"|\b(?:and|or|nor|as|so|than|then|plus|from|to|into|in|of|on|at|by|with|for)\b",
    re.IGNORECASE,
)
# A clause these words open denies, keeps, contrasts or supposes, so it states no removal.
_OPENERS = (
    r"but|while|whilst|though|although|except|apart|however|yet|whereas|kept|keep\w*|retain\w*"
    r"|remain\w*|still|not|nor|never|no|nothing|none|if|once|when|unless|until|after|before"
)
_BREAK = re.compile(rf"[,;:()]|(?=\b(?:{_OPENERS})\b|n['\u2019]t\b)", re.IGNORECASE)
_UNSTATED = re.compile(rf"\s*(?:\b(?:{_OPENERS})\b|n['\u2019]t\b)", re.IGNORECASE)
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+|\n+")
_AND = frozenset(FORMS[AND][0].split())
_REPLY = "Assistant: "


def _names(text: str) -> set[str]:
    """The words and digit runs of ``text`` that can name a fact."""
    return row_words(text) | set(digit_runs(text))


def _fact(row: str) -> set[str]:
    """The words both sides of a stored exchange say, with its digit runs."""
    person, _, reply = row.partition(_REPLY)
    return (row_words(person) & row_words(reply)) | set(digit_runs(row))


def _object(rest: str, facts: set[str], *, last: bool) -> str:
    """The text of ``rest`` to a joining word or quote mark, or all of it in a ``last`` clause
    when each item after a word for and opens with a word of ``facts`` and holds only those."""
    end = join = _JOIN.search(rest)
    while join is not None and join.group().lower() in _AND:
        following = _JOIN.search(rest, join.end())
        item = rest[join.end() : len(rest) if following is None else following.start()]
        if not item.split() or not _names(item.split()[0]) or not _names(item) <= facts:
            break
        join = following
    return rest if end is None or (join is None and last) else rest[: end.start()]


def _removed(clause: str, facts: set[str], *, last: bool) -> str:
    """The object a removal stated in ``clause`` names, to a joining word or quote mark."""
    stated = None if _UNSTATED.match(clause) else _GONE.search(clause)
    if stated is None:
        return ""
    if stated.group("after") is not None:
        return _object(clause[stated.end() :], facts, last=last)
    subject = clause[: stated.start()]
    return "" if _JOIN.search(subject) else subject


def false_sentence(reply: str, kept: Iterable[str], gone: Iterable[str]) -> str | None:
    """The first statement of ``reply`` saying a row of ``kept`` was forgotten, else ``None``.

    A word or digit run a row of ``gone``, the turn's deleted rows, holds names no kept row.
    """
    taken = set[str]().union(*map(_names, gone))
    facts = set[str]().union(*map(_fact, (*kept, *gone)))
    named = set[str]().union(*map(_fact, kept)) - taken
    for sentence in _SENTENCE_END.split(reply):
        if sentence.rstrip().endswith("?"):
            continue
        clauses = _BREAK.split(sentence)
        for index, clause in enumerate(clauses, 1):
            if not named.isdisjoint(_names(_removed(clause, facts, last=index == len(clauses)))):
                return sentence.strip()
    return None


def kept_claim(reply: str, taint: TaintLedger, runs: Sequence[ToolRun]) -> str | None:
    """The sentence of ``reply`` a kept note marks, ``None`` while a deleted row is unknown."""
    untrusted = any(run.ok and run.name == FORGET_UNTRUSTED_TOOL_NAME for run in runs)
    if untrusted or len(taint.forget_gone) < taint.forget_deleted:
        return None
    return false_sentence(reply, taint.forget_kept, taint.forget_gone)


def kept_claim_note(sentence: str, kept: Iterable[str], language: str = ENGLISH) -> str:
    """The kept note in ``language`` whose head names ``sentence`` as wrong about ``kept``."""
    head = in_language(KEPT_CLAIM_NOTE, KEPT_CLAIM_NOTES, language).format(sentence=sentence)
    return "\n".join([head, *(f"- {line}" for line in kept)]) + ")"
