"""How a rendered needle is looked for in a file, and what a file that lacks one is told.

Split out of `crosscheck.py`, which finds the declarations and reports the constants that do not
tie; this is the other half of a mention, what it means for a file to spend a rendered needle and
what to say when it does not. Nothing here reads a file or knows what a value is: it is handed the
needle, the text, and the spelling the value was rendered in.

**A needle is bounded at whichever edge is a word.** Bare containment had two passing violations
to prove it, a value that is a prefix of the one written down (`5005` inside `50051`) and a
published `host:container` pair whose host half alone carried the needle, so a rendered needle has
to appear as a token of its own and not merely somewhere inside a longer one.

**A point flanked by digits is inside a number**, which is the one thing a word edge cannot see.
A point is not a word character, so `10` used to be found in `10.09` and in `0.10` alike: the word
guard saw a space on one side and a point on the other, and both passed. The rule that tells those
from a number ending at a sentence's full stop reads the far side of the point rather than the
point itself, and it is one sentence read from both ends, so a digit edge takes a second guard
beside the word one. `2048.` closing a sentence still matches, the character past the point being
a space; `2048.5` does not. An edge that is a word but not a digit takes no such guard, `grpc.`
before a needle opening with a letter being attribute access and not a decimal.

**A needle is a value plus shape, and the shape is other people's text.** A template carries
enough neighbouring text to be a claim about the right sentence, and some of that text is another
constant's value: the compose publish's ``"{value}:{value}"`` opens with the host-side interface,
and most of the documents stating the seam port spell the address the body dials it at. Move one
of those neighbours and this needle is unfound, which used to be reported as the seam port not
being tied, sending a reader to a declaration that had not moved. The reader then had to diff the
needle against the file by hand to see which of its literals stopped matching, and a fault that
points at the wrong thing is worse than a thin one, because the reader trusts it (ADR-0023
bind-host addendum, which measured that misattribution).

So an unfound needle now says two things it can read rather than guess.

**Whether the value is still there.** If the file goes on spelling this constant's value as a
token of its own, then whatever stopped matching is shape, and the entry the fault names is
probably not the entry to change. That is the misattribution said out loud. It is a reading and
not a proof: a file may spell the same digits under two meanings, which is the same reason a
survey by number cannot be trusted, so the sentence says what was read and calls the conclusion a
maybe. A mention that renders only a name spells no value at all, and is told so instead.

**Where the file stops carrying the needle**, as the longest opening run of it the file contains.
That run pinpoints the divergence when the needle's shape is unique to it, and it is deliberately
measured over the whole file rather than one line, because the mention names a file and not a
line. A prefix satisfied on some other line therefore makes the run longer than the divergence in
the line the reader means: the compose publish's own interface moving still leaves `"127.0.0.1:`
carried, by the redis publish two dozen lines below. That is why the run is worded as the most of
the needle the file carries anywhere, which is exactly what it is, and why it is the second half
of the message rather than the first.
"""

import re

from couplings import PLACEHOLDER, Mention

# What counts as a continuation of a rendered needle's own token, at whichever of its two edges is
# itself made of one. A needle edged by punctuation (`var(--ceiling,`) needs no such guard.
WORD_CHARACTER = re.compile(r"\w")

# The narrower edge, and the only one a point can continue: a digit. The point is read from the
# needle outwards, so each guard asks for a digit on the FAR side of it, the near side being the
# needle's own edge. That is what keeps `2048.` at a full stop found and `2048.5` unfound, and it
# is why the two guards below are the same rule written twice rather than two rules.
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
    """The longest opening run of ``needle`` that ``text`` contains, which may be all of it.

    Plain containment rather than the bounded match above, deliberately: the question here is how
    far into the needle the file goes on agreeing, and a run that stops in the middle of a token is
    exactly the answer that question wants. Containment is monotone over a prefix, a shorter one
    sitting inside every longer one, so growing the run a character at a time finds the longest.
    """
    length = 0
    while length < len(needle) and needle[: length + 1] in text:
        length += 1
    return needle[:length]


def unfound(mention: Mention, needle: str, text: str, spelled: str) -> str:
    """Why ``text`` does not spend ``needle``, said as what of it the file does still carry.

    ``spelled`` is the value as it was rendered into the needle, which is the one part of that
    needle this constant answers for. Finding it still spelled as a token of its own is the
    evidence that what moved is shape and the fault is aimed at the wrong entry.
    """
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
