"""What a roster in a document names, read off the page."""

import re
from typing import NamedTuple

# A code span, and a bullet's own text. Both are deliberately small: what a roster is written in
# is one document's convention, and the shapes below are the whole of what this reads.
CODE_SPAN = re.compile(r"`([^`]+)`")
BULLET = re.compile(r"^ *[-*] +(.+)$")


class PassageError(Exception):
    """A document no longer carries the passage a roster is written in, or a bullet inside it."""


class Bulleted(NamedTuple):
    """One bullet per member, its name the bullet's first code span."""


class Spelled(NamedTuple):
    """Every code span in the passage matching ``pattern`` is a name the roster writes down."""

    pattern: re.Pattern[str]


class Bare(NamedTuple):
    """Every word matching ``pattern`` is a name, for a passage that carries no code spans."""

    pattern: re.Pattern[str]


Written = Bulleted | Spelled | Bare


def _once(text: str, phrase: str, which: str) -> int:
    """Return where ``phrase`` starts, refusing a boundary the document does not carry once."""
    found = text.count(phrase)
    if found != 1:
        msg = (
            f"the {which} phrase {phrase!r} appears {found} time(s); a passage is bounded by a "
            f"phrase its document carries exactly once"
        )
        raise PassageError(msg)
    return text.index(phrase)


def passage(text: str, opens: str, closes: str) -> str:
    """Return the run of ``text`` a roster is written in, between the two phrases bounding it."""
    start = _once(text, opens, "opening")
    end = _once(text, closes, "closing")
    if end <= start:
        msg = f"the closing phrase {closes!r} is written before the opening phrase {opens!r}"
        raise PassageError(msg)
    return text[start:end]


def _bulleted(text: str) -> list[str]:
    """Return the first code span of every bullet in ``text``, refusing a bullet without one."""
    found: list[str] = []
    for line in text.splitlines():
        bullet = BULLET.match(line)
        if bullet is None:
            continue
        span = CODE_SPAN.match(bullet.group(1))
        if span is None:
            msg = (
                f"the bullet {bullet.group(1)!r} opens with no name; a bulleted roster is one "
                f"bullet per member, opening with the name of it"
            )
            raise PassageError(msg)
        found.append(span.group(1))
    return found


def _inside_a_word(text: str, at: int) -> bool:
    """Whether ``text`` carries a word character at ``at``, which puts a match inside a word."""
    return 0 <= at < len(text) and (text[at].isalnum() or text[at] == "_")


def _bare(text: str, pattern: re.Pattern[str]) -> list[str]:
    """Return every whole word in ``text`` matching ``pattern``, in the order it carries them."""
    return [
        found.group(0)
        for found in pattern.finditer(text)
        if not _inside_a_word(text, found.start() - 1) and not _inside_a_word(text, found.end())
    ]


def names(text: str, written: Written) -> list[str]:
    """Return every name the roster in ``text`` writes down, in the order it writes them."""
    if isinstance(written, Spelled):
        spans = [span.group(1) for span in CODE_SPAN.finditer(text)]
        return [span for span in spans if written.pattern.fullmatch(span)]
    if isinstance(written, Bare):
        return _bare(text, written.pattern)
    return _bulleted(text)
