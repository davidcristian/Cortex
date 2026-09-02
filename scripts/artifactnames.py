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
not fail for the one fault it was built for. Each language is read for the mechanism that carries
a file to the engine in that language. A compose artifact is the item after one of llama.cpp's
own file flags, `ARTIFACT_FLAGS`, and a hosted one is a settings field the sidecar hands to its
resolver, the one method that joins a file onto the read-only mount, whichever keyword or flag
then spends the path it returns.

The short spelling of the model flag is deliberately not read. llama.cpp accepts `-m`, and
this tree starts an MCP sidecar with `python -m <module>`: a reader taking the item after every
`-m` as a model artifact would call a module name one and fail a correct service whose only
remedy would be to teach the gate, which costs more than the miss it would close. Every server
started here spells the flag in full, and a server that did not would still be found by the
wiring that dials it.

The resolver is read rather than the flags the sidecar writes, and rather than the field names.
The projector reaches the cortex tier's argv through its `extra`, assembled by a call the tier
reader does not approximate, and the flag in front of it is written on a local name bound one
statement earlier; the resolver call is handed the field directly, on the same line, in every
place an artifact is spent. A field name is a label its author chose (`cortex_mmproj_file` was
found by its suffix until 2026-09-02, and `cortex_mmproj_path` would have been found by nothing),
where a resolution is what the module does with the value. The domain is still the Python side
and never the variable under test, so an artifact misspelled in the environment is inside it.

Two shapes are refused rather than read around, each by name. A settings method other than the
resolver that reads the mount root would be a second resolver this reader does not read, so a path
joined onto the mount by hand is reported rather than missed. And a resolver handed no field at
all is a reading that would answer emptily forever: a renamed resolver takes every call with it,
and without this floor the tier reading would go on finding three artifacts while the projector
dropped out in silence.

An item that spends no variable names nothing this rule can hold. A model path written out in
full carries no name to misspell, and the membership readers already have their own answer for
that shape. So does a server whose artifact reaches it through its environment rather than its
argv: this reads what a command names, and the model host's own tiers are read from the sidecar's
declaration rather than from the passthrough that feeds it.

A server that serves no chat still names an artifact this rule holds. The CPU embedder runs
from the same llama.cpp image as the subagent servers, and what it serves is `subagentservers.py`'s
question rather than this one: that reader keeps it out of the subagent set on its own, by the
variable its argv spends and by a wiring that never dials it. An argv declaring `--embeddings` is
spelled no differently from any other, so there is no embedding exclusion here (ADR-0029's
addendum on a non-chat artifact naming itself in the family).
"""

import ast
from collections.abc import Mapping
from pathlib import Path
from typing import NamedTuple

from composedefaults import SubstitutionReadError, read_line
from composefiles import compose_files
from composestarts import ComposeStartError, Started, read_starts
from hostedtiers import (
    MODEL_MANAGER,
    SELF,
    SETTINGS_CLASS,
    TIER_MODULE,
    HostedTierError,
    aliases,
    declared,
    parse_module,
    tier_artifacts,
)

# llama.cpp's own flags naming the files a server loads, in the long spelling every server started
# here writes and the only one this reader takes: the model, and the multimodal projector loaded
# beside it. The engine has further file flags (a draft model, a LoRA adapter, a control vector),
# and a compose service spending a variable after one of those is unread until it is added here.
ARTIFACT_FLAGS = ("--model", "--mmproj")

# The sidecar's resolver, the one method that joins a file onto the read-only mount, and the field
# naming that mount. A settings field names an artifact when the module hands it to the resolver,
# and the mount may be read nowhere else, so a path joined by hand is refused rather than missed.
RESOLVER = "_path"
MOUNT_ROOT = "models_root"

# A resolver handed no field is a reading that would answer emptily forever.
MIN_RESOLVED = 1


class Artifact(NamedTuple):
    """One model artifact this tree names, and the variable a deployment names it under.

    ``where`` is the compose service whose argv names it, or the settings field the sidecar
    resolves it from, which is the word an author would search the file for. ``line`` is where
    the artifact is spent rather than where its name is declared: the service, the tier, or the
    call that resolves the field, which is the line the substitution reader is handed for its own
    refusals.
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
            if item in ARTIFACT_FLAGS and index + 1 < len(command)
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


def _reads(node: ast.AST, attribute: str) -> bool:
    """Whether ``node`` is ``self.<attribute>``, the one spelling a method reads a field in."""
    return (
        isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == SELF
        and node.attr == attribute
    )


def _methods(module: ast.Module) -> list[ast.FunctionDef]:
    """Every method of the settings class, in the order it writes them."""
    return [
        statement
        for node in module.body
        if isinstance(node, ast.ClassDef) and node.name == SETTINGS_CLASS
        for statement in node.body
        if isinstance(statement, ast.FunctionDef)
    ]


def _handed(call: ast.Call, named: Mapping[str, str]) -> list[str]:
    """Every settings field one resolver call is handed, however the expression wraps it."""
    return [
        node.attr
        for expression in (*call.args, *(keyword.value for keyword in call.keywords))
        for node in ast.walk(expression)
        if isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == SELF
        and node.attr in named
    ]


def resolved(module: ast.Module) -> tuple[tuple[str, str, int], ...]:
    """Every settings field the sidecar hands to its resolver, with the line it does so on.

    A field resolved twice is one artifact, reported where it is first resolved. The alias walk
    underneath decides what a field is named in the environment and raises on a settings class
    that names nothing.
    """
    named = aliases(module)
    found: dict[str, tuple[str, int]] = {}
    for method in _methods(module):
        if method.name != RESOLVER and any(_reads(node, MOUNT_ROOT) for node in ast.walk(method)):
            msg = (
                f"{TIER_MODULE} reads {MOUNT_ROOT} in {method.name} rather than in {RESOLVER}, so "
                "this reader cannot say which fields are resolved under the mount; join a path "
                f"onto the mount in {RESOLVER} only, or teach {Path(__file__).name} the shape"
            )
            raise HostedTierError(msg)
        calls = sorted(
            (
                node
                for node in ast.walk(method)
                if isinstance(node, ast.Call) and _reads(node.func, RESOLVER)
            ),
            key=lambda call: (call.lineno, call.col_offset),
        )
        for call in calls:
            for field in _handed(call, named):
                found.setdefault(field, (named[field], call.lineno))
    if len(found) < MIN_RESOLVED:
        msg = (
            f"{TIER_MODULE} hands no {SETTINGS_CLASS} field to {RESOLVER}, so no artifact could "
            "be found by where it is resolved and a reading of it could not fail"
        )
        raise HostedTierError(msg)
    return tuple((field, variable, line) for field, (variable, line) in found.items())


def tiered(root: Path) -> tuple[Artifact, ...]:
    """Every artifact the model host names, by the tiers that spend one and by the resolver.

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
            for field, variable, line in resolved(module)
            if field not in fields
        ),
    )


def named(root: Path) -> tuple[Artifact, ...]:
    """Every model artifact the tree under ``root`` names, the compose commands first."""
    return (*composed(root), *tiered(root))
