"""Every model artifact this tree names, and the variable each one is named under."""

import ast
from pathlib import Path
from typing import NamedTuple

from composedefaults import SubstitutionReadError, read_line
from composefiles import compose_files
from composestarts import ComposeStartError, Started, read_starts
from hostedtiers import (
    MODEL_MANAGER,
    SETTINGS_CLASS,
    TIER_MODULE,
    aliases,
    declared,
    parse_module,
    tier_artifacts,
)
from moduleconstants import bound

# llama.cpp's own flag naming the artifact a server serves, in the long spelling every server
# started here writes and the only one this reader takes.
MODEL_FLAG = "--model"

ARTIFACT_SUFFIX = "_file"


class Artifact(NamedTuple):
    """One model artifact this tree names, and the variable a deployment names it under."""

    file: str
    where: str
    line: int
    variable: str


def spends(started: Started) -> tuple[str, ...]:
    """Every variable one service's argv names a model artifact under, in the order written."""
    command = started.command or ()
    try:
        return tuple(
            spend.name
            for index, item in enumerate(command)
            if item == MODEL_FLAG and index + 1 < len(command)
            for spend in read_line(started.line, command[index + 1])
        )
    except SubstitutionReadError as err:
        msg = f"the command of {started.service!r} cannot be read: {err}"
        raise ComposeStartError(msg) from err


def _read(path: Path) -> str:
    """Read one compose file, naming it when it is absent or is not text."""
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as err:
        msg = f"cannot read {path}: {err}"
        raise ComposeStartError(msg) from err


def composed(root: Path) -> tuple[Artifact, ...]:
    """Every artifact a compose command under ``root`` names, in the order the tree is walked."""
    return tuple(
        Artifact(
            file=path.relative_to(root).as_posix(),
            where=started.service,
            line=started.line,
            variable=variable,
        )
        for path in compose_files(root)
        for started in read_starts(_read(path))
        for variable in spends(started)
    )


def files(module: ast.Module) -> tuple[tuple[str, str, int], ...]:
    """Every settings field whose own name says it holds an artifact, with its line."""
    named = aliases(module)
    return tuple(
        (field, named[field], statement.lineno)
        for node in module.body
        if isinstance(node, ast.ClassDef) and node.name == SETTINGS_CLASS
        for statement in node.body
        if (declaration := bound(statement)) is not None
        and (field := declaration[0]) in named
        and field.endswith(ARTIFACT_SUFFIX)
    )


def tiered(root: Path) -> tuple[Artifact, ...]:
    """Every artifact the model host names, by the tiers that spend one and by the fields.

    The tier walk first, so an artifact a tier reads its path from is reported at the tier that
    reads it; a field found both ways is one artifact and is not repeated.
    """
    module = parse_module(root, TIER_MODULE)
    named = aliases(module)
    shown = (MODEL_MANAGER / TIER_MODULE).as_posix()
    spent = tuple(
        Artifact(file=shown, where=field, line=call.lineno, variable=variable)
        for call in declared(module)
        for field, variable in tier_artifacts(call, named)
    )
    fields = {artifact.where for artifact in spent}
    return (
        *spent,
        *(
            Artifact(file=shown, where=field, line=line, variable=variable)
            for field, variable, line in files(module)
            if field not in fields
        ),
    )


def named(root: Path) -> tuple[Artifact, ...]:
    """Every model artifact the tree under ``root`` names, the compose commands first."""
    return (*composed(root), *tiered(root))
