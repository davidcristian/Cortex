"""The image a Dockerfile in this tree stands on, and the lines every reader of one here joins."""

import re
from collections.abc import Iterable, Mapping
from typing import NamedTuple

from composetargets import normalize
from imagevolumes import RECORD_PATH

# The instruction a stage opens with, matched case-insensitively the way docker matches it.
INSTRUCTION = "FROM"

# What separates the image a stage stands on from the name that stage is given, again however it
# is cased. A stage name is what a later `FROM` may stand on instead of an image.
STAGE = "AS"

# The one base that is not an image. A stage standing on it inherits nothing, so no row answers
# for it and none is asked for.
SCRATCH = "scratch"

# What a flag on the instruction opens with. `--platform` is the only one docker offers here, it
# says nothing about what the named image declares, and dropping it lets a file carrying one still
# answer rather than being refused for a token that changes no answer.
FLAG = "--"

# What ends a line that continues onto the next, in the default escape character. A file choosing
# another one is refused below rather than read under the wrong rule.
CONTINUES = "\\"

_ESCAPE = re.compile(r"^#[ \t]*escape[ \t]*=", re.IGNORECASE)

_UNROWED = (
    "{dockerfile} builds {reference!r} FROM {base!r}, which " + RECORD_PATH + " has no row for; "
    "what a built image inherits from its base is the half of its row this tree does not write, so "
    "an unrecorded base is an unasked question. Run `just image-volumes` to record what it "
    "declares."
)
_UNINHERITED = (
    "{dockerfile} builds {reference!r} FROM {base!r}, which declares VOLUME {path!r}, and the row "
    "for {reference!r} in " + RECORD_PATH + " does not carry it; a build from that base inherits "
    "the path, so every container of the rebuilt image takes an anonymous volume there while the "
    "record says the image declares nothing of the kind. Rebuild the image, run `just "
    "image-volumes` to record what it now declares, and mount something at the path."
)


class DockerfileError(Exception):
    """A Dockerfile carries a shape the readers of one in this tree will not guess at."""


class Inheritance(NamedTuple):
    """One Dockerfile's base as the gate found it: what it stands on, and what its row lacks."""

    bases: tuple[str, ...]
    faults: tuple[str, ...]


def logical(text: str) -> list[tuple[int, str]]:
    """The file's instructions, comments dropped and continuation lines joined onto their first."""
    joined: list[tuple[int, str]] = []
    carry = ""
    start = 0
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not joined and _ESCAPE.match(line):
            msg = f"line {number}: an escape directive changes what a continuation means"
            raise DockerfileError(msg)
        if not line or line.startswith("#"):
            continue
        if not carry:
            start = number
        if line.endswith(CONTINUES):
            carry += line[:-1]
            continue
        joined.append((start, carry + line))
        carry = ""
    if carry:
        joined.append((start, carry))
    return joined


def _stage(number: int, argument: str) -> tuple[str | None, str]:
    """One FROM as it names things: the stage name it gives, if any, and the image it stands on."""
    if "$" in argument:
        msg = f"line {number}: FROM {argument!r} carries an expansion only a build can resolve"
        raise DockerfileError(msg)
    written = [token for token in argument.split() if not token.startswith(FLAG)]
    if len(written) == 1:
        return None, written[0]
    if len(written) == 3 and written[1].upper() == STAGE:  # noqa: PLR2004 -- image, AS, name
        return written[2], written[0]
    msg = f"line {number}: FROM {argument!r} is not an image, optionally named with AS"
    raise DockerfileError(msg)


def read_base(text: str) -> str | None:
    """The image the final stage of one Dockerfile stands on, or None when it stands on nothing."""
    stages: list[tuple[str | None, str]] = []
    for number, line in logical(text):
        head, _, argument = line.partition(" ")
        if head.upper() == INSTRUCTION:
            stages.append(_stage(number, argument.strip()))
    if not stages:
        msg = "no FROM instruction, so nothing here says what this file is built on"
        raise DockerfileError(msg)
    order = {name.lower(): index for index, (name, _) in enumerate(stages) if name is not None}
    index = len(stages) - 1
    while True:
        reference = stages[index][1]
        target = order.get(reference.lower())
        if target is None:
            return None if reference == SCRATCH else reference
        if target >= index:
            msg = f"stage {reference!r} stands on itself or on one written after it"
            raise DockerfileError(msg)
        index = target


def inherited(
    dockerfile: str,
    text: str,
    reference: str,
    carried: Iterable[str],
    records: Mapping[str, tuple[str, ...]],
) -> Inheritance:
    """The base this file stands on, and every path its row carries that the built row lacks."""
    base = read_base(text)
    if base is None:
        return Inheritance((), ())
    row = records.get(base)
    if row is None:
        detail = _UNROWED.format(dockerfile=dockerfile, reference=reference, base=base)
        return Inheritance((base,), (detail,))
    held = set(carried)
    return Inheritance(
        (base,),
        tuple(
            _UNINHERITED.format(dockerfile=dockerfile, reference=reference, base=base, path=path)
            for path in row
            if normalize(path) not in held
        ),
    )
