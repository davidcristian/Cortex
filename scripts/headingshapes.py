"""How a markdown heading is read, and the shapes whose anchor this repo's rule cannot derive."""

import re
from typing import NamedTuple

from markdownfences import Fences

HEADING = re.compile(r"^#{1,6} +(\S.*?) *$")

CODE_SPAN = re.compile(r"`[^`]*`")

BRACKETED = re.compile(r"\[[^\]]*\]")
ANGLE_MARKUP = re.compile(r"<[A-Za-z/!?][^>]*>")
CLOSING_HASHES = re.compile(r"\s#+$")
UNDERSCORE_EMPHASIS = re.compile(r"(?:^|\W)_[^\s_][^_]*_(?:\W|$)")
ENTITY = re.compile(r"&(?:#\d+|#[xX][0-9a-fA-F]+|[A-Za-z][A-Za-z0-9]*);")

# One `=` or `-` under a paragraph line is enough to make it a heading, which is the spec rule
# and not a cautious reading of it.
SETEXT = re.compile(r"^ {0,3}(?:=+|-+)\s*$")

BLOCK_OPENER = re.compile(r"^\s*(?:[-*+]\s|\d+[.)]\s|>|\||#{1,6} )")

LINKED = "brackets a span, which markdown may make a link and this rule always reads literally"
TAGGED = "contains angle-bracket markup, whose letters this rule keeps and a renderer drops"
CLOSED = "is closed with hashes, which a renderer strips and this rule leaves as a trailing hyphen"
STRESSED = "emphasises with underscores, a word character to this rule and a mark to a renderer"
ENTITIED = "contains an entity reference, whose letters this rule keeps and a renderer resolves"
UNDERLINED = "is written as a setext underline, a heading shape this rule cannot see at all"
PLAINLY = "; write it as plain text under leading hashes, so the source is what a renderer slugs"

QUOTED = (
    "; quote the brackets in a code span, whose backticks this rule and a renderer both drop, "
    "or write the heading without them"
)


class Unsluggable(NamedTuple):
    """One heading whose anchor this rule cannot derive: where it is, and why not."""

    line: int
    heading: str
    reason: str


def headings(text: str) -> list[tuple[int, str]]:
    """Return every ATX heading outside a fenced block: its line number and its source text."""
    found: list[tuple[int, str]] = []
    fences = Fences()
    for number, line in enumerate(text.splitlines(), start=1):
        if fences.bounds(line):
            continue
        if not fences.inside and (match := HEADING.match(line)) is not None:
            found.append((number, match.group(1)))
    return found


def _inline_reason(heading: str) -> str | None:
    """Why one ATX heading's source text is refused, or None when this rule can slug it."""
    if CLOSING_HASHES.search(heading):
        return CLOSED
    bare = CODE_SPAN.sub("", heading)
    if BRACKETED.search(bare):
        return LINKED
    if ANGLE_MARKUP.search(bare):
        return TAGGED
    if UNDERSCORE_EMPHASIS.search(bare):
        return STRESSED
    if ENTITY.search(bare):
        return ENTITIED
    return None


def _underlined(text: str) -> list[Unsluggable]:
    """Return every setext heading in ``text``, reported at the underline that makes it one."""
    found: list[Unsluggable] = []
    previous = ""
    fences = Fences()
    for number, line in enumerate(text.splitlines(), start=1):
        if fences.bounds(line):
            previous = ""
            continue
        if fences.inside:
            previous = ""
            continue
        if SETEXT.match(line) and previous.strip() and not BLOCK_OPENER.match(previous):
            found.append(Unsluggable(line=number, heading=previous.strip(), reason=UNDERLINED))
        previous = line
    return found


def unsluggable(text: str) -> list[Unsluggable]:
    """Return every heading in ``text`` whose anchor this rule cannot derive, in order."""
    refused = [
        Unsluggable(line=number, heading=heading, reason=reason)
        for number, heading in headings(text)
        if (reason := _inline_reason(heading)) is not None
    ]
    return sorted([*refused, *_underlined(text)])


def _remedy(reason: str) -> str:
    """Return the remedy printed after ``reason``: the bracketed span's own, or the shared one."""
    return QUOTED if reason == LINKED else PLAINLY


def problems(name: str, text: str) -> list[str]:
    """Return one problem line per refused heading in ``text``, named for the file it is in."""
    return [
        f"{name}:{shape.line}: heading {shape.heading!r} {shape.reason}{_remedy(shape.reason)}"
        for shape in unsluggable(text)
    ]
