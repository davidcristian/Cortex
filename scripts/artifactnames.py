"""Every model artifact this tree names, and the variable each one is named under."""

from pathlib import Path
from typing import NamedTuple

from composedefaults import SubstitutionReadError, read_line
from composefiles import compose_files
from composestarts import ComposeStartError, Started, read_starts
from hostedtiers import (
    MODEL_MANAGER,
    TIER_MODULE,
    aliases,
    declared,
    parse_module,
    tier_artifacts,
)

# llama.cpp's own flag naming the artifact a server serves, in the long spelling every server
# started here writes and the only one this reader takes.
MODEL_FLAG = "--model"

# What an argv carrying either of these serves, which is not chat. Both spellings of the one flag,
# so the exclusion is dodged by neither, and it is llama.cpp that accepts both.
EMBEDDING_FLAGS = frozenset({"--embeddings", "--embedding"})


class Artifact(NamedTuple):
    """One model artifact this tree names, and the variable a deployment names it under."""

    file: str
    where: str
    line: int
    variable: str


def spends(started: Started) -> tuple[str, ...]:
    """Every variable one service's argv names a model artifact under, in the order written."""
    command = started.command or ()
    if any(item in EMBEDDING_FLAGS for item in command):
        return ()
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


def tiered(root: Path) -> tuple[Artifact, ...]:
    """Every artifact the model host's own tiers name, the subagent tier and the rest alike."""
    module = parse_module(root, TIER_MODULE)
    named = aliases(module)
    shown = (MODEL_MANAGER / TIER_MODULE).as_posix()
    return tuple(
        Artifact(file=shown, where=field, line=call.lineno, variable=variable)
        for call in declared(module)
        for field, variable in tier_artifacts(call, named)
    )


def named(root: Path) -> tuple[Artifact, ...]:
    """Every model artifact the tree under ``root`` names, the compose commands first."""
    return (*composed(root), *tiered(root))
