"""What a documented log line claims the brain prints, read off the page that prints it.

`samplecheck.py`'s doc side. This module turns a runbook's fenced sample back into the four things
the shipped formatter would have put on that line: the level, the logger, the message, and the
field names in the order they were printed. It reads markdown, imports nothing from the brain, and
compares nothing. `logcalls.py` is the other side, and the gate holds the two answers together.

**A sample is a fenced line and never a sentence.** A runbook writes a rendered line inside a
fence, where a reader takes it as output; the same text inside a paragraph is prose about a line
rather than a claim to have printed one. Reading prose would also make every inline mention owe a
field list, which would push a writer away from naming a line at all. So the walk toggles on a
fence marker and reads only what is inside one, and a sample the author meant to be checked is a
sample the author fenced.

**The line is found by its own prefix rather than by where it starts.** ``PlainFormatter`` writes
``LEVEL:logger:message`` and the decorations in front of that vary by what the runbook is showing:
compose prefixes each line with ``brain-1  | `` and a sample shown as the expected output of a
piped command is commented out with a ``#``. None of that is the line, so the prefix is searched
for rather than anchored, and whatever precedes it is decoration this module drops.

**Where the message stops is where the first field starts**, and that is a reading rather than a
parse. The formatter joins ``key=value`` pairs with a single space after the message, so the first
``name=`` token at a whitespace boundary is the field run's opening and everything before it is the
message. A message that itself spelled a ``word=`` would be cut short there, and the gate would
then report that no call site logs the message it read, which fails loudly and in the safe
direction: nothing in this tree writes such a message, and one that started to would be refused
rather than guessed at.

**Field names, never field values.** A sample's values are frequently placeholders (``<chat id>``,
``<what happened>``), and one runbook's captured ``port=50051`` is deliberately a dated reading
rather than a coupling, which the constant registry says in as many words. Values are also where a
real formatter and a hand-written sample legitimately differ: the formatter quotes every value
carrying whitespace and a placeholder standing in for one need not. So this reader takes the names
and drops the rest, and the gate is about which fields a line carries and in what order.

**A quoted value cannot open a field.** The formatter quotes any value carrying whitespace or a
quote of its own, so an ``=`` inside a quoted run belongs to that value and not to the line. A
candidate is therefore accepted only where an even number of quotes stands in front of it, which is
the same rule a reader applies by eye and the only one that keeps a JSON argument from being read
as a field.

**A sample may wrap, because a rendered line is longer than a page.** A trailing backslash is how
every runbook here continues one, so a wrapped sample is joined back into the one line it stands
for before anything is read off it. The continuation's own decoration needs no rule: a comment
marker spells no ``name=``, so it lands between two fields as text this reader already ignores. The
join stops at a fence, so a backslash on the last line of a block cannot swallow the block's end.
"""

import re
from typing import NamedTuple

# A fenced block, spelled the way markdown spells it. Either fence character toggles, and an info
# string (```text) is still a fence.
FENCE = re.compile(r"^\s*(?:```|~~~)")

# The prefix ``PlainFormatter`` writes in front of every line: the level, the logger's dotted name,
# and then the message. Searched rather than anchored, so a compose prefix or a shell comment
# marker in front of it is decoration rather than a reason to miss the line.
SAMPLE = re.compile(
    r"(?P<level>DEBUG|INFO|WARNING|ERROR|CRITICAL)"
    r":(?P<logger>[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*)"
    r":(?P<rest>.*)$"
)

# One field opening: a name at a whitespace boundary, followed by the ``=`` the formatter writes.
# The name shape is a Python identifier, which is what an ``extra=`` key has to be to survive as a
# record attribute.
FIELD = re.compile(r"(?:^|(?<=\s))(?P<name>[A-Za-z_]\w*)=")

# How a sample says it continues on the next line. The runbooks spell it the way a shell does.
CONTINUED = re.compile(r"\\\s*$")

# What a continuation line carries in front of the text that continues the line above: the marker
# commenting a sample out inside a shell block, and the indent lining the wrap up under it. It is
# dropped rather than ignored because it would otherwise sit between the message and the first
# field, and where the message stops is the one reading that cannot step over decoration.
DECORATION = re.compile(r"^[\s#]+")

# What the formatter puts around a value that carries whitespace or a quote, and therefore what
# tells a field boundary from an ``=`` inside somebody's value.
QUOTE = '"'


class Sample(NamedTuple):
    """One rendered log line a document prints back to a reader.

    ``fields`` is the field names in printed order, which is name order whenever the line came
    out of the shipped formatter. Values are deliberately absent: the gate over this asks which
    fields a line carries, and a sample's values are placeholders as often as they are readings.
    """

    line: int
    level: str
    logger: str
    message: str
    fields: tuple[str, ...]


def opens_field(text: str, at: int) -> bool:
    """Whether the candidate at ``at`` stands outside every quoted value on the line."""
    return text.count(QUOTE, 0, at) % 2 == 0


def field_names(text: str) -> tuple[str, ...]:
    """Every field name ``text`` opens, in the order it opens them."""
    return tuple(
        found["name"] for found in FIELD.finditer(text) if opens_field(text, found.start())
    )


def split_fields(rest: str) -> tuple[str, tuple[str, ...]]:
    """The message and the field names in ``rest``, split where the first field opens."""
    for found in FIELD.finditer(rest):
        if opens_field(rest, found.start()):
            return rest[: found.start()].strip(), field_names(rest[found.start() :])
    return rest.strip(), ()


def joined(lines: list[str], start: int) -> str:
    """``lines[start]`` with every line it continues onto folded back into one.

    A fence ends the join whatever the backslash says, so a sample continued off the end of its
    own block cannot absorb the marker that closes it.
    """
    text = lines[start]
    at = start
    while CONTINUED.search(text) and at + 1 < len(lines) and not FENCE.match(lines[at + 1]):
        at += 1
        text = f"{CONTINUED.sub('', text)} {DECORATION.sub('', lines[at]).strip()}"
    return text


def samples(text: str) -> list[Sample]:
    """Every log line ``text`` prints inside a fenced block, read as what it claims to render."""
    lines = text.splitlines()
    fenced = False
    found: list[Sample] = []
    for number, line in enumerate(lines, start=1):
        if FENCE.match(line):
            fenced = not fenced
            continue
        if not fenced:
            continue
        printed = SAMPLE.search(joined(lines, number - 1))
        if printed is None:
            continue
        message, fields = split_fields(printed["rest"])
        found.append(
            Sample(
                line=number,
                level=printed["level"],
                logger=printed["logger"],
                message=message,
                fields=fields,
            )
        )
    return found
