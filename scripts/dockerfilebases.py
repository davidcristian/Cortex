"""The image a Dockerfile in this tree is built from, and the line joining its readers share."""

import re
from collections.abc import Iterable, Mapping
from typing import NamedTuple

from composetargets import normalize
from imagevolumes import RECORD_PATH, Row

INSTRUCTION = "FROM"

STAGE = "AS"

SCRATCH = "scratch"

FLAG = "--"

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
    "for {reference!r} in " + RECORD_PATH + " does not contain it; a build from that base inherits "
    "the path, so every container of the rebuilt image takes an anonymous volume there while the "
    "record says the image declares nothing of the kind. Rebuild the image, run `just "
    "image-volumes` to record what it now declares, and mount something at the path."
)


class DockerfileError(Exception):
    """A Dockerfile has a form the readers in this tree cannot read."""


class Inheritance(NamedTuple):
    """One Dockerfile's base: the image it is built from, and what its recorded row lacks."""

    bases: tuple[str, ...]
    triggers: tuple[str, ...]
    faults: tuple[str, ...]


def logical(text: str) -> list[tuple[int, str]]:
    """The file's instructions, comments dropped and continuation lines joined onto their first."""
    joined: list[tuple[int, str]] = []
    pending = ""
    start = 0
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not joined and _ESCAPE.match(line):
            msg = f"line {number}: an escape directive changes what a continuation means"
            raise DockerfileError(msg)
        if not line or line.startswith("#"):
            continue
        if not pending:
            start = number
        if line.endswith(CONTINUES):
            pending += line[:-1]
            continue
        joined.append((start, pending + line))
        pending = ""
    if pending:
        joined.append((start, pending))
    return joined


def _stage(number: int, argument: str) -> tuple[str | None, str]:
    """One FROM: the stage name it gives, if any, and the image or stage it is built from."""
    if "$" in argument:
        msg = f"line {number}: FROM {argument!r} contains an expansion only a build can resolve"
        raise DockerfileError(msg)
    written = [token for token in argument.split() if not token.startswith(FLAG)]
    if len(written) == 1:
        return None, written[0]
    if len(written) == 3 and written[1].upper() == STAGE:  # noqa: PLR2004 -- image, AS, name
        return written[2], written[0]
    msg = f"line {number}: FROM {argument!r} is not an image, optionally named with AS"
    raise DockerfileError(msg)


def read_base(text: str) -> str | None:
    """The image the final stage of one Dockerfile is built from, or None when there is none."""
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
    row_paths: Iterable[str],
    records: Mapping[str, Row],
) -> Inheritance:
    """The base this file is built from, and every path in its row that the built row lacks."""
    base = read_base(text)
    if base is None:
        return Inheritance((), (), ())
    row = records.get(base)
    if row is None:
        detail = _UNROWED.format(dockerfile=dockerfile, reference=reference, base=base)
        return Inheritance((base,), (), (detail,))
    held = set(row_paths)
    return Inheritance(
        (base,),
        row.onbuild,
        tuple(
            _UNINHERITED.format(dockerfile=dockerfile, reference=reference, base=base, path=path)
            for path in row.volumes
            if normalize(path) not in held
        ),
    )
