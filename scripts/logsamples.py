"""What a documented log line claims the brain prints, read off the page that prints it."""

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

DECORATION = re.compile(r"^[\s#]+")

# What the formatter puts around a value that carries whitespace or a quote, and therefore what
# tells a field boundary from an ``=`` inside somebody's value.
QUOTE = '"'


class Sample(NamedTuple):
    """One rendered log line a document prints back to a reader."""

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
