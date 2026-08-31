"""Every model artifact this tree names, and the variable each one is named under.

`flagcheck.py` holds every subagent server this repo starts to the flags its tier requires, and
both readers of that set answer "is this one" out of a single string, the `MODEL_PREFIX` of
`subagentservers.py`: a compose command spends a variable beginning that way, or a hosted tier's
`model_path` is aliased to one. That reading is exact for the artifacts written down today and
says nothing about the one written tomorrow. A subagent artifact named
`CORTEX_SUBAGENT_MODEL_FILE_CPU` is the same artifact under a variable neither reader looks at, so
the server or tier it names is left out of both sets with nothing reported.

This module answers the question underneath that one. The two set readers ask what a declaration
says; this one asks whether every declaration of its kind is named so that it can be found at all.
It returns every model artifact the tree names, in both places one is named, and the rule in
`flagcheck.py` holds each to beginning `subagentservers.FAMILY_PREFIX`, which is what makes the
membership reading above it decidable.

The artifacts are found structurally, never by the prefix. A rule whose domain was the
variables that already begin `CORTEX_MODEL_FILE_` would be a rule about the very convention it
checks: the misspelling it exists to catch is outside that domain by construction, so it could
not fail for the one fault it was built for. A compose artifact is therefore the item after
llama.cpp's own `--model`, and a hosted one is the settings field a tier reads its `model_path`
from, which is the reading `hostedtiers.py` already makes with its subagent filter turned off.

The short spelling of the model flag is deliberately not read. llama.cpp accepts `-m`, and
this tree starts an MCP sidecar with `python -m <module>`: a reader taking the item after every
`-m` as a model artifact would call a module name one and fail a correct service whose only
remedy would be to teach the gate, which costs more than the miss it would close. Every server
started here spells the flag in full, and a server that did not would still be found by the
wiring that dials it.

A settings field is read for what its own name says it holds as well as for where it is spent. A
tier's `model_path` is one keyword of several that carry an artifact into an argv, and the
multimodal projector reaches the cortex tier through its `extra` instead, assembled by a call the
tier reader does not approximate. So the hosted side is read a second way, off the field names
the settings class declares: a field whose own name ends `ARTIFACT_SUFFIX` names an artifact
whichever keyword spends it, and one found both ways is one artifact rather than two. That domain
is the sidecar's own Python-side convention and not the variable under test, so an artifact
misspelled in the environment is still inside it, which is the property the whole reading needs.

An item that spends no variable names nothing this rule can hold. A model path written out in
full carries no name to misspell, and the membership readers already have their own answer for
that shape. So does a server whose artifact reaches it through its environment rather than its
argv: this reads what a command names, and the model host's own tiers are read from the sidecar's
declaration rather than from the passthrough that feeds it.

A server that serves no chat still names an artifact this rule holds. The CPU embedder runs
from the same llama.cpp image as the subagent servers, and what it serves is `subagentservers.py`'s
question rather than this one: that reader keeps it out of the subagent set on its own, by the
variable its argv spends and by a wiring that never dials it. This reader asks the question
underneath, whether an artifact is spelled so such an answer is decidable at all, and an argv
declaring `--embeddings` is spelled no differently from any other. So there is no embedding
exclusion here, and the one that used to sit here excused the single artifact in this tree spelled
outside the family, in the very block a new non-chat model server would be copied from
(ADR-0029's addendum on a non-chat artifact naming itself in the family).

No floor of its own is asserted, because one is asserted underneath. `hostedtiers.py` raises on a
sidecar declaring no tier and on a tier naming no artifact, so a tree this reader can read at all
names at least one artifact, and a reading that answered emptily forever is already impossible.
"""

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

# What a settings field's own name says about what it holds. Every artifact field the sidecar
# declares spells it, the projector's included, and nothing else there does: a binary and a mount
# root are paths without being artifacts. It is deliberately the Python name and not the
# environment one, that being the spelling under test.
ARTIFACT_SUFFIX = "_file"


class Artifact(NamedTuple):
    """One model artifact this tree names, and the variable a deployment names it under.

    ``where`` is the compose service whose argv names it, or the settings field a hosted tier
    reads its path from, which is the word an author would search the file for. ``line`` is where
    that declaration opens rather than where the name itself is written, the service or the tier,
    which is the line the substitution reader is handed for its own refusals.
    """

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
    """Every settings field whose own name says it holds an artifact, with its line.

    The alias walk underneath decides what a field is named in the environment and raises on a
    settings class that names nothing; this adds only the two things that walk drops, which field a
    name belongs to and where it is written.
    """
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
