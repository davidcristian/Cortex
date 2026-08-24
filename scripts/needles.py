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

**Whether the value is still there, and where it read one.** If the file goes on spelling this
constant's value as a token of its own, then whatever stopped matching is shape, and the entry the
fault names is probably not the entry to change. That is the misattribution said out loud. It is a
reading and not a proof: a file may spell the same digits under two meanings, which is the same
reason a survey by number cannot be trusted, so the sentence says what was read and calls the
conclusion a maybe. A mention that renders only a name spells no value at all, and is told so
instead.

A maybe a reader cannot check is a grep, which is the work this reading exists to save, so the
yes carries the line it was read on and the words around it. Three things are said, and each is
chosen rather than cheapest:

- **Which occurrence**, when the file spells the value more than once: the one nearest where the
  run below stops. The two readings a fault carries are about the same divergence, so aiming them
  at one place makes the message one sentence instead of two, and it is the only choice that
  spends what the run already computed. A needle opening with its own value degenerates to the
  first occurrence, the run then starting where the value does, and that is honest rather than a
  failure: there is no shape in front of the value to be nearer to. A file carrying no part of the
  needle has no run at all, and the first occurrence is what the message then names.
- **The line, and the words on it.** A line number alone turns the grep into a jump, which is
  worth having and is not enough in a log nobody can jump from: the reading that dismissed the
  case that opened this (`~11 GB` in a paragraph about VRAM) is the sentence and not the number.
  Nor could proximity have dismissed it. That homonym is seventy one lines from the needle's own
  line and sits one line above a sentence that does name the constant, which is why the nearest
  occurrence is only a tie break between matches and the words are the verdict. So the line's own
  text comes with it, windowed around the match, because a runbook table row is several hundred
  characters and a fault is one sentence.
- **How many places spell it.** "Spelled in eleven places" is itself the answer that the reading
  proves nothing, and it costs one number.

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

# How many characters of the line a still-spelled value sits on are quoted back with it. Wide
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

    Plain containment rather than the bounded match above, deliberately: the question here is how
    far into the needle the file goes on agreeing, and a run that stops in the middle of a token is
    exactly the answer that question wants. Containment is monotone over a prefix, a shorter one
    sitting inside every longer one, so growing the run a character at a time finds the longest.
    """
    length = 0
    while length < len(needle) and needle[: length + 1] in text:
        length += 1
    return needle[:length]


def nearest(text: str, run: str, matches: list[re.Match[str]]) -> re.Match[str]:
    """The match closest to anywhere ``text`` carries ``run``, or the first when it carries none.

    Distance is in characters rather than in lines, which needs no line index and orders two
    matches on one line the way a reader would. Every occurrence of the run is an anchor, because
    a run is a prefix and a file may satisfy it on a line the reader does not mean; the nearest
    value to any of them is still the best guess this fault can make about which line diverged.
    """
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
    matches = list(bounded(spelled).finditer(text))
    if not matches:
        return f"{stem}, {held}; the file does not spell {spelled!r} as a token of its own either"
    return (
        f"{stem}, {held}; the file does still spell {spelled!r} as a token of its own"
        f"{where(text, run, matches)}, so what moved is likely shape this needle carries rather "
        "than this value, and the constant to change may not be the one named here"
    )
