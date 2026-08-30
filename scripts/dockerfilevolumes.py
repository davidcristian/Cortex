"""What a Dockerfile in this tree declares a VOLUME at, and each one its recorded row lacks.

`imagevolumes.py` holds what docker said each image declares, and `volumecheck.py` holds every
declared path to a mount. Three of those rows are images this repo builds from Dockerfiles of its
own, and for those the record can move under the gate from inside the tree: add
`VOLUME /var/cache/thing` to `brain/Dockerfile` and the built image declares a path, every
container of it collects an anonymous volume, and the row goes on saying the image declares
nothing, with `just check` green until somebody rebuilds and hand-runs `just image-volumes`. This
module is the half of that question the tree can answer on every commit, with no daemon.

**The rule is one-directional, and that is what makes it cheap.** Every path a Dockerfile here
declares must appear in the row for the image built from it. A recorded path that Dockerfile does
not declare is fine: it came from the base image the file stands on, which is `dockerfilebases.py`'s
question and the other half of what a built row says. That module is asked from here, over the same
text and inside the same read, so a file opened once answers both halves and an unreadable one is
reported once.

**Which Dockerfile builds which row is read from the compose file, never recorded.** The mapping
lives in each service's `build:` stanza, `composeservices.py` reads it there, and the gate hands it
over. Writing it down beside the row would buy cheapness by spelling one fact twice, with nothing
deriving it to compare, which is the same defect this check exists to close one level down.

**Where a relative context lands** depends on the project directory, which compose takes from
`--project-directory` when it is given and from the first `-f` file's own directory otherwise, so
both are tried, exactly as `bindcheck.py` tries both for a bind source. A Dockerfile landing under
neither is a fault rather than a silent pass.

**What a `VOLUME` looks like.** Both spellings are read, the JSON array `VOLUME ["/a", "/b"]` and
the plain list `VOLUME /a /b`, joined across continuation lines. `ONBUILD VOLUME` is deliberately
not one of them, and that refusal is a correctness requirement rather than a simplification: it
declares a volume in an image built *from* this one, so reading it here would make the rule above
demand a path in the row for an image that truly declares none, and redden a correct record.
Everything else is refused rather than walked past, the way every reader here refuses: an argument
carrying a build argument or an environment variable, which only a build can resolve; a path that
is not absolute; an array that is not one, or that names something other than a path; and a
`VOLUME` naming nothing. The file's own grammar, the comment and continuation handling and the
`escape=` parser directive that would change what a continuation means, is `dockerfilebases.py`'s,
shared because both readers work over the same joined lines.

**The same grammar reads a base's triggers**, which is the third source a built row answers for. A
base carrying `ONBUILD VOLUME /x` declares nothing of its own and makes the image built `FROM` it
declare `/x`, so its row records the trigger raw and `dockerfilebases.py` hands it over here: each
entry is one whole instruction as docker wrote it down, read as the one-line Dockerfile it is, and
every path it names must appear in the built row exactly as an inherited one must. A trigger this
reader cannot read is a fault rather than a resolved-to-nothing, for the reason a skipped `VOLUME`
would be: it is a path the next build may declare and this tree would go on denying.
"""

import json
import os
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import NamedTuple, cast

from composeservices import Build
from composetargets import normalize
from dockerfilebases import DockerfileError, Inheritance, inherited, logical
from imagevolumes import RECORD_PATH, Row

# The instruction this reader is looking for, matched case-insensitively the way docker matches it.
INSTRUCTION = "VOLUME"

# What opens a JSON container, which is how the array spelling of the instruction begins. Both are
# dispatched to the array reader, because an object where an array belongs is a shape to refuse
# with the reason rather than to hand to the path splitter and refuse for the wrong one.
JSON_OPENERS = ("[", "{")

_UNDECLARED = (
    "{dockerfile} declares VOLUME {path!r}, and the row for {reference!r} in "
    + RECORD_PATH
    + " does not carry it; every container of that image then takes an anonymous volume there "
    "while the record says the image declares nothing. Rebuild the image, run `just "
    "image-volumes` to record what it now declares, and mount something at the path."
)
_NOWHERE = (
    "the image {reference!r} is built from {context!r}, where no {dockerfile} lands under either "
    "project directory compose can pick; the row for it in " + RECORD_PATH + " then describes an "
    "image nothing here builds. Point the build stanza at the file that builds it."
)
_UNRESOLVED = (
    "the image {reference!r} is built from {written!r}, which carries a substitution only a build "
    "can resolve, so nothing here can read what that file declares. Write the path out."
)
_UNREADABLE = "{dockerfile} builds {reference!r} and could not be read: {detail}"
_UNTRIGGERED = (
    "{dockerfile} builds {reference!r} FROM {base!r}, whose ONBUILD declares VOLUME {path!r}, and "
    "the row for {reference!r} in " + RECORD_PATH + " does not carry it; the trigger fires during "
    "the next build from that base, so the rebuilt image declares the path and every container of "
    "it takes an anonymous volume there while the record says the image declares nothing of the "
    "kind. Rebuild the image, run `just image-volumes` to record what it now declares, and mount "
    "something at the path."
)
_UNREADABLE_TRIGGER = (
    "{dockerfile} builds {reference!r} FROM {base!r}, whose recorded ONBUILD this reader will not "
    "guess at: {detail}. A trigger nobody can read is a path the next build may declare and this "
    "tree would go on denying."
)


class Reading(NamedTuple):
    """One build stanza followed: the files it reached, what they stand on, and every fault."""

    dockerfiles: tuple[str, ...]
    bases: tuple[str, ...]
    faults: tuple[str, ...]


def _array(number: int, argument: str) -> list[str]:
    """The paths a JSON-array VOLUME names, refused whole when it is not an array of paths."""
    try:
        loaded: object = json.loads(argument)
    except json.JSONDecodeError as err:
        msg = f"line {number}: VOLUME {argument!r} is not a JSON array: {err}"
        raise DockerfileError(msg) from err
    if not isinstance(loaded, list):
        msg = f"line {number}: VOLUME {argument!r} is not a JSON array"
        raise DockerfileError(msg)
    written: list[str] = []
    for item in cast("list[object]", loaded):
        if not isinstance(item, str):
            msg = f"line {number}: VOLUME {argument!r} names {item!r}, which is not a path"
            raise DockerfileError(msg)
        written.append(item)
    return written


def _paths(number: int, argument: str) -> list[str]:
    """The container paths one VOLUME instruction names, in either spelling docker accepts."""
    if "$" in argument:
        msg = f"line {number}: VOLUME {argument!r} carries an expansion only a build can resolve"
        raise DockerfileError(msg)
    written = _array(number, argument) if argument.startswith(JSON_OPENERS) else argument.split()
    if not written:
        msg = f"line {number}: VOLUME names no path"
        raise DockerfileError(msg)
    for path in written:
        if not path.startswith("/"):
            msg = f"line {number}: VOLUME path {path!r} is not an absolute container path"
            raise DockerfileError(msg)
    return [normalize(path) for path in written]


def read_volumes(text: str) -> tuple[str, ...]:
    """Every container path one Dockerfile declares a VOLUME at, in the order it writes them."""
    found: list[str] = []
    for number, line in logical(text):
        head, _, argument = line.partition(" ")
        if head.upper() != INSTRUCTION:
            continue
        found.extend(_paths(number, argument.strip()))
    return tuple(found)


def onbuild_volumes(entries: Iterable[str]) -> tuple[str, ...]:
    """Every path a base's recorded ONBUILD triggers would declare in the image built from it.

    Each entry is one whole instruction as docker wrote it down, with any continuation already
    joined by the builder that recorded it, so it is read as the one-line Dockerfile it is: an
    entry naming another instruction declares no volume, exactly as a `RUN` in a file declares
    none, and a `VOLUME` this reader cannot read is refused rather than resolved to nothing.

    An entry not opening with an instruction word is refused too, and that is the one refusal
    aimed at the hand rather than at docker. The row is pasted in by whoever ran the recipe, and
    a trigger written as the path it resolves to, `/x` where docker said `VOLUME /x`, would
    otherwise be read as an instruction this reader passes over and would declare nothing at all.
    """
    found: list[str] = []
    for entry in entries:
        head, _, _argument = entry.partition(" ")
        if not head.isalpha():
            msg = f"ONBUILD {entry!r} does not open with an instruction docker would have written"
            raise DockerfileError(msg)
        found.extend(read_volumes(entry))
    return tuple(found)


def _triggered(
    dockerfile: str, reference: str, stands: Inheritance, carried: set[str]
) -> list[str]:
    """Every path this file's base would declare through a trigger that its row does not carry."""
    faults: list[str] = []
    for base in stands.bases:
        try:
            paths = onbuild_volumes(stands.triggers)
        except DockerfileError as err:
            faults.append(
                _UNREADABLE_TRIGGER.format(
                    dockerfile=dockerfile, reference=reference, base=base, detail=err
                )
            )
            continue
        faults.extend(
            _UNTRIGGERED.format(
                dockerfile=dockerfile, reference=reference, base=base, path=path_here
            )
            for path_here in paths
            if path_here not in carried
        )
    return faults


def landings(root: Path, compose: Path, build: Build) -> list[Path]:
    """Every place the Dockerfile a service builds from lands, over both project directories."""
    projects = [root] if compose.parent == root else [root, compose.parent]
    found: list[Path] = []
    for project in projects:
        landed = Path(os.path.normpath(project / build.context / build.dockerfile))
        if landed.is_file() and landed not in found:
            found.append(landed)
    return found


def undeclared(
    root: Path,
    compose: Path,
    build: Build,
    reference: str,
    recorded: tuple[str, ...],
    records: Mapping[str, Row],
) -> Reading:
    """Every path the Dockerfile behind ``reference`` declares or inherits that its row lacks.

    The halves are asked over one read of the file, since a build's own declarations, the base it
    stands on and what that base would trigger are questions about the same text, and a file that
    cannot be read owes one fault rather than three.
    """
    if "$" in build.context or "$" in build.dockerfile:
        written = f"{build.context}/{build.dockerfile}"
        return Reading((), (), (_UNRESOLVED.format(reference=reference, written=written),))
    found = landings(root, compose, build)
    if not found:
        detail = _NOWHERE.format(
            reference=reference, context=build.context, dockerfile=build.dockerfile
        )
        return Reading((), (), (detail,))
    carried = {normalize(path) for path in recorded}
    read: list[str] = []
    bases: list[str] = []
    faults: list[str] = []
    for path in found:
        name = Path(os.path.relpath(path, root)).as_posix()
        read.append(name)
        try:
            text = path.read_text(encoding="utf-8")
            paths = read_volumes(text)
            stands = inherited(name, text, reference, carried, records)
        except (OSError, UnicodeDecodeError, DockerfileError) as err:
            faults.append(_UNREADABLE.format(dockerfile=name, reference=reference, detail=err))
            continue
        bases.extend(stands.bases)
        faults.extend(stands.faults)
        faults.extend(_triggered(name, reference, stands, carried))
        faults.extend(
            _UNDECLARED.format(dockerfile=name, path=path_here, reference=reference)
            for path_here in paths
            if path_here not in carried
        )
    return Reading(tuple(read), tuple(bases), tuple(faults))
