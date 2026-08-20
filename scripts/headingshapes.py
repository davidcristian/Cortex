"""How a markdown heading is read, and the shapes whose anchor this repo's rule will not guess.

Split out of `backloganchors.py` when the refusal below took it past the line cap, along the
seam that was already there: that file answers which anchors a document offers and which
pointers land, and this one answers the prior question of what a heading even is here.

The slug rule next door reads a heading's **source** text. A renderer slugs the **rendered**
text, and the two agree exactly when every markdown construct in the source is built from
characters that rule already drops and carries no text away with it. Plain prose, punctuation,
code spans and `*` emphasis all qualify: a backtick and an asterisk are dropped on both sides
and take nothing with them, which is why a heading quoting an identifier slugs identically
either way.

Six shapes do not qualify, and every one of them makes the rule read a heading MORE literally
than a renderer does:

- **a bracketed span**, with or without a target after it. Where a target follows, a renderer
  slugs the bracketed text alone and the rule slugs the text and the target both, welding a path
  onto the anchor. Where none does, the span is a link exactly when a definition elsewhere in the
  document names its label, which is the one question a heading cannot answer about itself, so
  the whole shape is refused rather than the half a target marks. The price is a literal pair of
  brackets in a heading, which no heading in this tree spends;
- **angle-bracket markup**, an HTML tag or an autolink, whose letters the rule keeps as text;
- **a closing run of hashes**, which markdown allows and a renderer strips, where the rule
  turns the space before them into a trailing hyphen;
- **underscore emphasis**, the underscore being a word character to the rule and a formatting
  mark to a renderer. An underscore inside a word is neither, and never reported: CommonMark
  does not read one as emphasis, so both sides keep it;
- **an entity reference**, whose letters the rule keeps where a renderer resolves the whole of
  it to one character;
- **a setext underline**, which is invisible to the ATX reader below, so a document written
  that way offers no anchors at all and every pointer into it reads as broken.

They are **refused by name rather than emulated.** Rendering a heading's inline markdown before
slugging it costs about what refusing costs, but it is a transform written against shapes the
tree does not contain, and a wrong transform yields a wrong anchor, which is a silent accept the
gate could never see. A refusal is loud in both directions: a shape reported here is a heading
somebody must rewrite, and a shape missed here leaves the old approximation exactly where it
was. That asymmetry is the whole argument.
"""

import re
from typing import NamedTuple

HEADING = re.compile(r"^#{1,6} +(\S.*?) *$")
FENCE = re.compile(r"^\s*(?:```|~~~)")

# A code span renders as its own literal text, and its backticks are dropped by the slug rule
# and by a renderer alike, so nothing inside one can make the two disagree. Stripped before the
# inline shapes below are looked for, so a heading that *quotes* a link or an entity is left be.
CODE_SPAN = re.compile(r"`[^`]*`")

# The five inline shapes, each looked for in a heading whose code spans are already gone, except
# the closing hashes, which are read off the raw text they trail. The bracketed span is deliberately
# blind to what follows it: an inline link, an image and both reference forms are all found by the
# brackets alone, and so is the shortcut form, which carries no mark of its own at all.
BRACKETED = re.compile(r"!?\[[^\]]*\]")
ANGLE_MARKUP = re.compile(r"<[A-Za-z/!?][^>]*>")
CLOSING_HASHES = re.compile(r"\s#+$")
UNDERSCORE_EMPHASIS = re.compile(r"(?:^|\W)_[^\s_][^_]*_(?:\W|$)")
ENTITY = re.compile(r"&(?:#\d+|#[xX][0-9a-fA-F]+|[A-Za-z][A-Za-z0-9]*);")

# The sixth shape. A rule of `=` or `-` under a paragraph line is a setext heading, indented at
# most three spaces, and a single character of either is enough: that is the spec's rule and not
# a conservative reading of it, since a lone dash under prose really does render as a heading.
SETEXT = re.compile(r"^ {0,3}(?:=+|-+)\s*$")

# A line that opens a block of its own is not the paragraph text a setext rule underlines, so a
# rule of dashes below one is a thematic break instead. A blank predecessor is checked separately,
# which is what separates a break written after a blank line from a heading written without one.
BLOCK_OPENER = re.compile(r"^\s*(?:[-*+]\s|\d+[.)]\s|>|\||#{1,6} )")

# What each refused shape is told, and the remedy all six share. Constants so a test names the
# sentence the gate prints rather than a paraphrase of it that could drift from the gate's own.
LINKED = "brackets a span, which markdown may make a link and this rule always reads literally"
TAGGED = "carries angle-bracket markup, whose letters this rule keeps and a renderer drops"
CLOSED = "is closed with hashes, which a renderer strips and this rule leaves as a trailing hyphen"
STRESSED = "emphasises with underscores, a word character to this rule and a mark to a renderer"
ENTITIED = "carries an entity reference, whose letters this rule keeps and a renderer resolves"
UNDERLINED = "is written as a setext underline, a heading shape this rule cannot see at all"
PLAINLY = "; write it as plain text under leading hashes, so the source is what a renderer slugs"


class Unsluggable(NamedTuple):
    """One heading whose anchor this rule will not guess at: where it is, and why not."""

    line: int
    heading: str
    reason: str


def headings(text: str) -> list[tuple[int, str]]:
    """Return every ATX heading outside a fenced block: its line number and its source text."""
    found: list[tuple[int, str]] = []
    fenced = False
    for number, line in enumerate(text.splitlines(), start=1):
        if FENCE.match(line):
            fenced = not fenced
            continue
        if not fenced and (match := HEADING.match(line)) is not None:
            found.append((number, match.group(1)))
    return found


def _inline_reason(heading: str) -> str | None:
    """Why this rule refuses one ATX heading's source text, or None when it can slug it.

    The closing hashes are read first and off the raw text, since stripping code spans could
    uncover or bury a trailing run; the rest are read off the heading without its code spans.
    """
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
    fenced = False
    for number, line in enumerate(text.splitlines(), start=1):
        if FENCE.match(line):
            fenced = not fenced
            previous = ""
            continue
        if fenced:
            previous = ""
            continue
        if SETEXT.match(line) and previous.strip() and not BLOCK_OPENER.match(previous):
            found.append(Unsluggable(line=number, heading=previous.strip(), reason=UNDERLINED))
        previous = line
    return found


def unsluggable(text: str) -> list[Unsluggable]:
    """Return every heading in ``text`` whose anchor this rule refuses to guess at, in order."""
    refused = [
        Unsluggable(line=number, heading=heading, reason=reason)
        for number, heading in headings(text)
        if (reason := _inline_reason(heading)) is not None
    ]
    return sorted([*refused, *_underlined(text)])


def problems(name: str, text: str) -> list[str]:
    """Return one problem line per refused heading in ``text``, named for the file it is in."""
    return [
        f"{name}:{shape.line}: heading {shape.heading!r} {shape.reason}{PLAINLY}"
        for shape in unsluggable(text)
    ]
