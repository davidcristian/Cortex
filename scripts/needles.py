"""How a rendered needle is looked for in a file, and what a file that lacks one is told.

Split out of `crosscheck.py`, which finds the declarations and reports the constants that do not
tie; this is the other half of a mention, what it means for a file to spend a rendered needle and
what to say when it does not. Nothing here reads a file or knows what a value is: it is handed the
needle, the text, and the spelling the value was rendered in.

**A needle is bounded at whichever edge is a word.** Bare containment had two passing violations
to prove it, a value that is a prefix of the one written down (`5005` inside `50051`) and a
published `host:container` pair whose host half alone carried the needle, so a rendered needle has
to appear as a token of its own and not merely somewhere inside a longer one.

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


def bounded(needle: str) -> re.Pattern[str]:
    """The needle as a pattern no longer token can contain: a word edge may not touch a word."""
    lead = r"(?<!\w)" if WORD_CHARACTER.match(needle[:1]) else ""
    trail = r"(?!\w)" if WORD_CHARACTER.match(needle[-1:]) else ""
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
