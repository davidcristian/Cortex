"""How a rendered needle is looked for in a file, and what a file that lacks one is told."""

import re

from couplings import PLACEHOLDER, Mention

# What counts as a continuation of a rendered needle's own token, at whichever of its two edges is
# itself made of one. A needle edged by punctuation (`var(--ceiling,`) needs no such guard.
WORD_CHARACTER = re.compile(r"\w")

DIGIT = re.compile(r"\d")

# The lookarounds each edge may take, in the order they are applied: the word guard both kinds of
# word edge need, then the decimal guard only a digit edge does.
LEAD_GUARDS = (r"(?<!\w)", r"(?<!\d\.)")
TRAIL_GUARDS = (r"(?!\w)", r"(?!\.\d)")

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
    """The longest opening run of ``needle`` that ``text`` contains, which may be all of it."""
    length = 0
    while length < len(needle) and needle[: length + 1] in text:
        length += 1
    return needle[:length]


def nearest(text: str, run: str, matches: list[re.Match[str]]) -> re.Match[str]:
    """The match closest to anywhere ``text`` carries ``run``, or the first when it carries none."""
    anchors = [found.start() for found in re.finditer(re.escape(run), text)] if run else []
    if not anchors:
        return matches[0]
    return min(matches, key=lambda match: min(abs(match.start() - at) for at in anchors))


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


def where(text: str, run: str, matches: list[re.Match[str]]) -> str:
    """Where ``text`` goes on spelling the value: how many places, and the words at the one meant.

    Worded to follow "spells it as a token of its own", so the sentence the reader gets names a
    line to open and reads back what is on it.
    """
    match = nearest(text, run, matches)
    number = text.count("\n", 0, match.start()) + 1
    opened = text.rfind("\n", 0, match.start()) + 1
    ends = text.find("\n", match.start())
    closed = len(text) if ends < 0 else ends
    read = quote(text[opened:closed], match.start() - opened, match.end() - opened)
    if len(matches) == 1:
        return f", once on line {number}, which reads {read!r}"
    which = "the nearest to that run" if run else "the first"
    return f", in {len(matches)} places, {which} on line {number}, which reads {read!r}"


def unfound(mention: Mention, needle: str, text: str, spelled: str) -> str:
    """Why ``text`` does not spend ``needle``, said as what of it the file does still carry."""
    run = carried(needle, text)
    stem = f"{mention.path} does not spell {needle!r} as a token of its own"
    if run == needle:
        return f"{stem}, carrying it only inside a longer token"
    held = f"carrying no more of it than {run!r}" if run else "carrying no part of it"
    if PLACEHOLDER not in mention.template:
        return f"{stem}, {held}; this needle renders no value, so the whole of it is shape"
    matches = list(bounded(spelled).finditer(text))
    if not matches:
        return f"{stem}, {held}; the file does not spell {spelled!r} as a token of its own either"
    return (
        f"{stem}, {held}; the file does still spell {spelled!r} as a token of its own"
        f"{where(text, run, matches)}, so what moved is likely shape this needle carries rather "
        "than this value, and the constant to change may not be the one named here"
    )
