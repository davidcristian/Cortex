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


def unfound(mention: Mention, needle: str, text: str, spelled: str) -> str:
    """Why ``text`` does not spend ``needle``, said as what of it the file does still carry."""
    run = carried(needle, text)
    stem = f"{mention.path} does not spell {needle!r} as a token of its own"
    if run == needle:
        return f"{stem}, carrying it only inside a longer token"
    held = f"carrying no more of it than {run!r}" if run else "carrying no part of it"
    if PLACEHOLDER not in mention.template:
        return f"{stem}, {held}; this needle renders no value, so the whole of it is shape"
    if bounded(spelled).search(text):
        return (
            f"{stem}, {held}; the file does still spell {spelled!r} as a token of its own, so "
            "what moved is likely shape this needle carries rather than this value, and the "
            "constant to change may not be the one named here"
        )
    return f"{stem}, {held}; the file does not spell {spelled!r} as a token of its own either"
