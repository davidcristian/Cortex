"""The image a Dockerfile in this tree stands on, and the lines every reader of one here joins.

A built image declares the union of two things, and only one of them is written in this tree.
`dockerfilevolumes.py` reads the `VOLUME` instructions the file itself carries. Everything else in
the row for a built image arrived from the base its final stage stands on, which is a fact about a
registry and moves without anything here changing. Recording those bases in `imagevolumes.py` is
what lets a re-derivation refresh them the way it refreshes every other pulled reference, and this
module says which base a built row is answerable for and holds the row to what that base declares.

**Measured rather than assumed**, with docker on 2026-08-28. An image built from a base declaring
`/probe/base` declares `/probe/base` itself, so a declaration really is inherited through `FROM`.
A `FROM ... AS builder` stage declaring `/probe/builder` contributed nothing to the built image,
because only the final stage's config survives a build. That is why the last `FROM` is the one this
reader resolves, and why `brain/Dockerfile`'s `uv` builder stage gets no row of its own: whatever
that stage declares, no container ever runs it.

**A stage may stand on an earlier stage**, so the last `FROM` is followed back through the stage
names written before it until it reaches something that is not one, which is the image the build
really pulls. Stage names are matched however they are cased, the way docker matches them.
`FROM scratch` stands on nothing and is answered as such rather than sent looking for a row.

**Why the file's grammar sits here.** A stage cannot be found before comments are dropped and
continuation lines are joined onto the instruction they belong to, so `logical` and
`DockerfileError` live beside the reader that needs them first, and `dockerfilevolumes.py` reads
its own instructions out of the same joined lines. Both readers refuse a shape they were not
taught rather than walking past it, and for the same reason: a `FROM` guessed at is a base whose
declarations the record would go on denying. A flag on the instruction is the one thing dropped
rather than refused, `--platform` being docker's only one and changing nothing about what the
named image declares.

**The rule is one-directional**, like the one over the file's own declarations: every path the
base's row carries must appear in the row for the image built from that file. A recorded path the
base does not declare is fine, being the Dockerfile's own. What it catches is the half the built
rows cannot catch themselves. Those three are asked without a pull, having no registry, so their
answer is whatever the machine running the recipe last built, while the base rows are pulled on
every re-derivation. A base republished with a new `VOLUME` therefore reddens `just check` on the
next run of the recipe, rather than waiting for somebody to rebuild on the machine that runs it.

**A base declares for its children too**, through `ONBUILD VOLUME`, which its own `Config.Volumes`
never carries and the build of anything standing `FROM` it does. That is the second dimension of a
base's row and it costs the built row the same paths, so the reading is handed straight over: this
module says which base answers for a built row and returns the triggers that row recorded, and
`dockerfilevolumes.py` reads them with the `VOLUME` grammar it already owns and reports what the
built row does not carry. One rule, two sources, and the parsing where the parser lives.
"""

import re
from collections.abc import Iterable, Mapping
from typing import NamedTuple

from composetargets import normalize
from imagevolumes import RECORD_PATH, Row

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
    """One Dockerfile's base as the gate found it: what it stands on, and what its row lacks.

    ``bases`` is empty only for a file standing on `scratch`, and carries the base even when no row
    answers for it: the reference is one the record has to hold either way, so the gate counts it
    among the images it named before deciding whether the record knows it. ``triggers`` is the raw
    `ONBUILD` the base's row recorded, belonging to the one base in ``bases`` and handed to the
    caller that owns the `VOLUME` grammar; it is empty for a base standing outside the record,
    whose fault is already reported here.
    """

    bases: tuple[str, ...]
    triggers: tuple[str, ...]
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
    """The image the final stage of one Dockerfile stands on, or None when it stands on nothing.

    Only the final stage decides, every earlier one having been measured to contribute nothing to
    the built image, and a final stage naming an earlier one is followed back to what that stage
    stands on. The walk only ever moves to an earlier index, so it terminates; a stage naming
    itself or one written after it is a file no build could resolve and is refused rather than
    read as an image reference that happens to share a stage's name.
    """
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
    records: Mapping[str, Row],
) -> Inheritance:
    """The base this file stands on, and every path its row carries that the built row lacks."""
    base = read_base(text)
    if base is None:
        return Inheritance((), (), ())
    row = records.get(base)
    if row is None:
        detail = _UNROWED.format(dockerfile=dockerfile, reference=reference, base=base)
        return Inheritance((base,), (), (detail,))
    held = set(carried)
    return Inheritance(
        (base,),
        row.onbuild,
        tuple(
            _UNINHERITED.format(dockerfile=dockerfile, reference=reference, base=base, path=path)
            for path in row.volumes
            if normalize(path) not in held
        ),
    )
