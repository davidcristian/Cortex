"""What a roster in a document names, read off the page.

`rostercheck.py` compares the names read here with the real set `rostermembers.py` reads out of the
tree. A roster is written the way its document reads best, so a name is matched in three forms:

- **bulleted**, one bullet per member with its name the bullet's first code span, which is how a
  list that explains each member is written. A bullet in the passage that opens with no code span
  raises rather than being skipped, since skipping one would leave a member outside the roster
  with nothing reported.
- **spelled**, every code span in the passage matching the roster's own pattern, which is how a
  roster written as a running sentence is read. The pattern belongs to the roster, so the prose
  around the names may put anything else it likes in backticks.
- **bare**, every word in the passage matching that pattern with no code span around it, which is
  how a roster written in a fenced block is read: a repo map is plain text laid out in columns,
  and a backtick inside it is literal text. This form works only inside a bounded passage, since a
  bare `linecap.py` in ordinary prose matches wherever it falls, and it needs a guard the other two
  get from their delimiters: a match touching a word character on either side sits inside a longer
  word and is not a name.

A passage is bounded by two phrases the document already carries, each exactly once. Bounding by
heading would put both rosters in the `scripts/` contract into one section, where a name missing
from one list and present in the other would pass; bounding by paragraph cannot reach a list that
opens with a fenced command. A phrase that stops appearing, or starts appearing twice, raises,
because the boundary of a roster is part of what the roster claims.

Fences are not read. A bullet inside a fenced block in a passage is read as a bullet like any
other, so a bulleted roster whose passage grows one fails rather than passing quietly. Reading
fences would add a fourth markdown-fence parser to this tree, which the backlog records as
something to unify rather than to grow.
"""

import re
from typing import NamedTuple

# A code span, and a bullet's own text. Both patterns are small because a roster is written in one
# document's convention rather than in the whole of markdown.
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
    """Return where ``phrase`` starts, raising unless the document carries it exactly once."""
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
    """Return the first code span of every bullet in ``text``, raising on a bullet without one."""
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
