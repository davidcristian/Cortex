"""Every model artifact this tree names, and the variable each one is named under."""

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

# llama.cpp has further file flags (a draft model, a LoRA adapter, a control vector); a variable
# written after one of those is not read until it is added here.
ARTIFACT_FLAGS = ("--model", "--mmproj")

RESOLVER = "_path"
MOUNT_ROOT = "models_root"

MIN_RESOLVED = 1


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
    """Whether ``node`` is ``self.<attribute>``, the one form a method reads a field in."""
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
    """Every settings field the sidecar hands to its resolver, with the line it does so on."""
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
    """Every artifact the model host names, by the tiers that spend one and by the resolver."""
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
