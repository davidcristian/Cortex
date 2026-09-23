"""How a rendered search text is looked for in a file, and what a fault says when it is missing."""

import re
from typing import NamedTuple

from couplings import PLACEHOLDER, Mention
from linereadings import LineRun, line_of, line_runs, quote, said

WORD_CHARACTER = re.compile(r"\w")

DIGIT = re.compile(r"\d")

# The decimal guard asks for a digit on the far side of the point, which keeps `2048.` at a full
# stop found and `2048.5` unfound.
LEAD_GUARDS = (r"(?<!\w)", r"(?<!\d\.)")
TRAIL_GUARDS = (r"(?!\w)", r"(?!\.\d)")

VALUE = "value"
NAME = "name"

MET = (
    "so what moved is likely shape this search text has rather than this {part}, and the constant "
    "to change may not be the one named here"
)
APART = (
    "and no run stops on that line, so what moved is not settled here: a file is free to write "
    "these characters under another meaning, which is what its own prose does with a value that "
    "is an ordinary word"
)


def _guard(edge: str, guards: tuple[str, str]) -> str:
    """The lookaround one edge of the search text needs: none, the word one, or both."""
    word, decimal = guards
    if not WORD_CHARACTER.match(edge):
        return ""
    return f"{word}{decimal}" if DIGIT.match(edge) else word


def bounded(search_text: str) -> re.Pattern[str]:
    """The search text as a pattern no longer token contains: a word edge may not touch a word."""
    lead = _guard(search_text[:1], LEAD_GUARDS)
    trail = _guard(search_text[-1:], TRAIL_GUARDS)
    return re.compile(f"{lead}{re.escape(search_text)}{trail}")


def longest_prefix(search_text: str, text: str) -> str:
    """The longest opening run of ``search_text`` that ``text`` contains, which may be all of it."""
    length = 0
    while length < len(search_text) and search_text[: length + 1] in text:
        length += 1
    return search_text[:length]


def anchors(text: str, run: str) -> list[int]:
    """Every offset where ``text`` stops matching ``run``, and none at all when it matches none."""
    return [found.end() for found in re.finditer(re.escape(run), text)] if run else []


def nearest(ends: list[int], matches: list[re.Match[str]]) -> tuple[re.Match[str], int | None]:
    """The closest value and run stop, or the first value and no stop when there is no run."""
    if not ends:
        return matches[0], None
    pairs = ((match, at) for match in matches for at in ends)
    return min(pairs, key=lambda pair: abs(pair[0].start() - pair[1]))


def where(text: str, match: re.Match[str], places: int, *, anchored: bool) -> str:
    """Where ``text`` writes the value again: how many places, and the words at the one meant."""
    number = line_of(text, match.start())
    opened = text.rfind("\n", 0, match.start()) + 1
    ends = text.find("\n", match.start())
    closed = len(text) if ends < 0 else ends
    read = quote(text[opened:closed], match.start() - opened, match.end() - opened)
    if places == 1:
        return f", once on line {number}, which reads {read!r}"
    which = "the nearest to that run" if anchored else "the first"
    return f", in {places} places, {which} on line {number}, which reads {read!r}"


def stops(text: str, run: str, ends: list[int], at: int | None) -> str:
    """How much of ``search_text`` ``text`` contains, and where the occurrence meant stops."""
    if not run:
        return "with no part of it"
    held = f"with no more of it than {run!r}"
    line = line_of(text, (ends[0] if at is None else at) - 1)
    if len(ends) == 1:
        return f"{held}, which stops on line {line}"
    which = "the first" if at is None else "the nearest to that form"
    return f"{held}, which stops in {len(ends)} places, {which} on line {line}"


def conclusion(text: str, match: re.Match[str], at: int | None, part: str) -> str:
    """What the two readings conclude: the strong form only where they name one line."""
    if at is None or line_of(text, at - 1) != line_of(text, match.start()):
        return APART
    return MET.format(part=part)


def _stopped(
    text: str,
    search_text: str,
    run: str,
    read: tuple[list[LineRun] | None, list[int]],
    at: int | None,
) -> str:
    """The run clause: per line for a one-line ``search_text``, over the whole file otherwise."""
    runs, ends = read
    return stops(text, run, ends, at) if runs is None else said(runs, search_text, at)


class Answered(NamedTuple):
    """The part of the search text its constant supplies, and what a fault calls that part."""

    written: str
    word: str


def answered(mention: Mention, written: str) -> Answered:
    """Which half of the rendered search text this constant supplies: its value, or its name."""
    if PLACEHOLDER in mention.template or mention.name is None:
        return Answered(written, VALUE)
    return Answered(mention.name, NAME)


def unfound(mention: Mention, search_text: str, text: str, written: str) -> str:
    """Why ``text`` does not contain ``search_text``, said as how much of it the file still has."""
    run = longest_prefix(search_text, text)
    stem = f"{mention.path} does not write {search_text!r} as a token of its own"
    if run == search_text:
        return f"{stem}, having it only inside a longer token"
    runs = line_runs(search_text, text, bounded(search_text))
    ends = anchors(text, run) if runs is None else [each.stop for each in runs]
    held = answered(mention, written)
    matches = list(bounded(held.written).finditer(text))
    if not matches:
        stopped = _stopped(text, search_text, run, (runs, ends), None)
        return (
            f"{stem}, {stopped}; the file does not write {held.written!r} as a token of its own "
            f"either"
        )
    match, at = nearest(ends, matches)
    return (
        f"{stem}, {_stopped(text, search_text, run, (runs, ends), at)}; the file does still write "
        f"{held.written!r} as a "
        f"token of its own{where(text, match, len(matches), anchored=bool(ends))}, "
        f"{conclusion(text, match, at, held.word)}"
    )
