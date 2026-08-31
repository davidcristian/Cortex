"""How a rendered needle is looked for in a file, and what a fault says when one is not found.

Split out of `crosscheck.py`, which finds the declarations and reports the constants that do not
tie. Nothing here reads a file or knows what a value is: it is handed the needle, the text, and the
spelling the value was rendered in.

A needle must appear as a token of its own rather than inside a longer one, bare containment having
passed two real violations: a value that is a prefix of the one written down (`5005` inside
`50051`), and a published `host:container` pair whose host half alone carried the needle. A digit
edge takes a second guard against a decimal point, so `2048.` closing a sentence still matches
while `2048.5` does not (ADR-0029 bounded-matching addendum).

A needle is a value plus shape, and some of that shape is another constant's value, so a neighbour
moving leaves the needle unfound and the fault names a constant that did not move (ADR-0023
bind-host addendum, which measured that misattribution). An unfound needle therefore carries two
readings: whether the file still spells this constant's value as a token of its own, with the line
number and the words on that line, and how much of the needle the file carries anywhere, with the
line where that run stops. The two are picked together as the ends of one distance, measured in
characters so that two matches on one line order the way a reader would, and both fall back to the
first occurrence when there is nothing to be nearest to. The message says which rule produced each
line. The distance itself is not stated: two line numbers are the comparison, and a gap in lines
would sometimes disagree with the pick, which was made in characters.
"""

import re

from couplings import PLACEHOLDER, Mention

# What counts as a continuation of a rendered needle's own token, at whichever of its two edges is
# itself made of one. A needle edged by punctuation (`var(--ceiling,`) needs no such guard.
WORD_CHARACTER = re.compile(r"\w")

# The narrower edge, and the only one a point can continue: a digit. Each guard asks for a digit on
# the far side of the point, the near side being the needle's own edge, which is what keeps `2048.`
# at a full stop found and `2048.5` unfound.
DIGIT = re.compile(r"\d")

# The lookarounds each edge may take, in the order they are applied: the word guard both kinds of
# word edge need, then the decimal guard only a digit edge does.
LEAD_GUARDS = (r"(?<!\w)", r"(?<!\d\.)")
TRAIL_GUARDS = (r"(?!\w)", r"(?!\.\d)")

# How many characters of the line a still-written value sits on are quoted back with it. Wide
# enough to carry the sentence the value is spent in, which is what tells a homonym from the real
# thing, and bounded because the widest line this gate reads is over a thousand characters of
# runbook table row and a fault is one sentence.
QUOTED_WIDTH = 100

# What marks a quote that starts or stops inside its line, so a reader reads a window rather than
# a sentence the file does not have.
TRIMMED = "..."


def _guard(edge: str, guards: tuple[str, str]) -> str:
    """The lookaround one edge of a needle needs: none, the word one, or that and the decimal."""
    word, decimal = guards
    if not WORD_CHARACTER.match(edge):
        return ""
    return f"{word}{decimal}" if DIGIT.match(edge) else word


def bounded(needle: str) -> re.Pattern[str]:
    """The needle as a pattern no longer token can contain: a word edge may not touch a word.

    A digit edge may not touch a point with a digit past it either, that point being a decimal
    one rather than a sentence's.
    """
    lead = _guard(needle[:1], LEAD_GUARDS)
    trail = _guard(needle[-1:], TRAIL_GUARDS)
    return re.compile(f"{lead}{re.escape(needle)}{trail}")


def carried(needle: str, text: str) -> str:
    """The longest opening run of ``needle`` that ``text`` contains, which may be all of it.

    Plain containment rather than the bounded match above, since a run that stops in the middle of
    a token is the answer wanted here. Containment is monotone over a prefix, so growing the run
    one character at a time finds the longest.
    """
    length = 0
    while length < len(needle) and needle[: length + 1] in text:
        length += 1
    return needle[:length]


def anchors(text: str, run: str) -> list[int]:
    """Every offset ``text`` stops carrying ``run`` at, and none at all when it carries none.

    The stop rather than the start, because the run stops where the file stops agreeing with the
    needle. Measuring from the start put the whole length of the run into every distance.
    """
    return [found.end() for found in re.finditer(re.escape(run), text)] if run else []


def nearest(ends: list[int], matches: list[re.Match[str]]) -> tuple[re.Match[str], int | None]:
    """The closest value and run stop, or the first value and no stop when there is no run.

    Every occurrence of the run is an anchor, a run being a prefix that a file may satisfy on a
    line the reader does not mean. The pair is chosen once and both halves are reported, so the
    two lines the message names are the ends of one distance rather than two independent picks.
    """
    if not ends:
        return matches[0], None
    pairs = ((match, at) for match in matches for at in ends)
    return min(pairs, key=lambda pair: abs(pair[0].start() - pair[1]))


def line_of(text: str, at: int) -> int:
    """The one-based line the offset ``at`` falls on."""
    return text.count("\n", 0, at) + 1


def quote(line: str, start: int, end: int) -> str:
    """``line`` around the match at ``start``..``end``, trimmed to a width a fault can carry."""
    if len(line.strip()) <= QUOTED_WIDTH:
        return line.strip()
    margin = max(QUOTED_WIDTH - (end - start), 0) // 2
    opened = max(start - margin, 0)
    closed = min(end + margin, len(line))
    lead = "" if opened == 0 else TRIMMED
    trail = "" if closed == len(line) else TRIMMED
    return f"{lead}{line[opened:closed].strip()}{trail}"


def where(text: str, match: re.Match[str], places: int, *, anchored: bool) -> str:
    """Where ``text`` goes on spelling the value: how many places, and the words at the one meant.

    Worded to follow "spells it as a token of its own", so the sentence the reader gets names a
    line to open and reads back what is on it.
    """
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
    """How much of the needle ``text`` carries, and where the occurrence meant stops.

    ``at`` is the stop the value reading was measured against, when there is one. Without it the
    first stop is named and said to be the first, the same fallback the value reading makes.
    """
    if not run:
        return "carrying no part of it"
    held = f"carrying no more of it than {run!r}"
    line = line_of(text, (ends[0] if at is None else at) - 1)
    if len(ends) == 1:
        return f"{held}, which stops on line {line}"
    which = "the first" if at is None else "the nearest to that spelling"
    return f"{held}, which stops in {len(ends)} places, {which} on line {line}"


def unfound(mention: Mention, needle: str, text: str, spelled: str) -> str:
    """Why ``text`` does not spend ``needle``, said as what of it the file does still carry.

    ``spelled`` is the value as it was rendered into the needle, the one part of that needle this
    constant answers for. Finding it still written as a token of its own is the evidence that what
    moved is shape and that the fault names the wrong entry.
    """
    run = carried(needle, text)
    stem = f"{mention.path} does not spell {needle!r} as a token of its own"
    if run == needle:
        return f"{stem}, carrying it only inside a longer token"
    ends = anchors(text, run)
    if PLACEHOLDER not in mention.template:
        held = stops(text, run, ends, None)
        return f"{stem}, {held}; this needle renders no value, so the whole of it is shape"
    matches = list(bounded(spelled).finditer(text))
    if not matches:
        held = stops(text, run, ends, None)
        return f"{stem}, {held}; the file does not spell {spelled!r} as a token of its own either"
    match, at = nearest(ends, matches)
    return (
        f"{stem}, {stops(text, run, ends, at)}; the file does still spell {spelled!r} as a token "
        f"of its own{where(text, match, len(matches), anchored=bool(ends))}, so what moved is "
        "likely shape this needle carries rather than this value, and the constant to change may "
        "not be the one named here"
    )
