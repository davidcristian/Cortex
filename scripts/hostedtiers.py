"""Which tiers the model host starts as subagents, read off the sidecar's own declaration."""

import ast
from collections.abc import Mapping
from pathlib import Path
from typing import NamedTuple

from moduleconstants import ModuleReadError, bound, constants, items, parse, text
from subagentservers import MODEL_PREFIX

MODEL_MANAGER = Path("brain/packages/model_manager/src/cortex_model_manager")
ARGV_MODULE = "tiers.py"
TIER_MODULE = "config.py"

ARGV_FUNCTION = "llama_server_argv"
TIER_CLASS = "TierArgs"
TIER_EXTRA = "extra"
TIER_PATH = "model_path"
SETTINGS_CLASS = "ModelHostConfig"
SETTINGS_FIELD = "Field"
SETTINGS_ALIAS = "validation_alias"
SELF = "self"

UNREADABLE = "<computed>"

MIN_TIERS = 1
MIN_ALIASES = 1


class HostedTierError(Exception):
    """The sidecar's tier declarations cannot be read, or say something this reader cannot."""


class Tier(NamedTuple):
    """One hosted tier serving subagents, and the command the supervisor would start it with."""

    file: str
    named: str
    line: int
    command: tuple[str, ...]


def parse_module(root: Path, name: str) -> ast.Module:
    """One of the sidecar's modules, with the syntax reader's error re-raised as this module's."""
    try:
        return parse(root / MODEL_MANAGER / name, (MODEL_MANAGER / name).as_posix())
    except ModuleReadError as err:
        raise HostedTierError(str(err)) from err


def _returned(module: ast.Module) -> ast.Tuple:
    """The tuple the argv builder returns, raising on a shape this reader cannot splice into."""
    for statement in module.body:
        if not isinstance(statement, ast.FunctionDef) or statement.name != ARGV_FUNCTION:
            continue
        written = [node for node in ast.walk(statement) if isinstance(node, ast.Return)]
        tuples = [node.value for node in written if isinstance(node.value, ast.Tuple)]
        if len(tuples) == 1 and len(written) == 1:
            return tuples[0]
        msg = (
            f"{ARGV_FUNCTION} does not return exactly one tuple, so this reader cannot say which "
            "argv a tier is started with"
        )
        raise HostedTierError(msg)
    msg = f"{ARGV_MODULE} declares no {ARGV_FUNCTION}, so no tier's command can be read"
    raise HostedTierError(msg)


def shared(module: ast.Module) -> tuple[tuple[str | None, ...], tuple[str | None, ...]]:
    """What every tier's command includes before and after its own extra flags."""
    returned = _returned(module)
    strings, _ = constants(module)
    splatted = [isinstance(item, ast.Starred) for item in returned.elts]
    at = [
        index
        for index, item in enumerate(returned.elts)
        if isinstance(item, ast.Starred)
        and isinstance(item.value, ast.Attribute)
        and item.value.attr == TIER_EXTRA
    ]
    if len(at) != 1 or sum(splatted) != 1:
        msg = (
            f"{ARGV_FUNCTION} does not splat a tier's {TIER_EXTRA} exactly once, so this reader "
            "cannot say where a tier's own flags end up in its command"
        )
        raise HostedTierError(msg)
    return (
        tuple(text(item, strings) for item in returned.elts[: at[0]]),
        tuple(text(item, strings) for item in returned.elts[at[0] + 1 :]),
    )


def aliases(module: ast.Module) -> dict[str, str]:
    """Every settings field naming an environment variable, and the variable each one names."""
    named: dict[str, str] = {}
    for statement in module.body:
        if not isinstance(statement, ast.ClassDef) or statement.name != SETTINGS_CLASS:
            continue
        for field in statement.body:
            declared = bound(field)
            if declared is None or not isinstance(call := declared[1], ast.Call):
                continue
            if not isinstance(call.func, ast.Name) or call.func.id != SETTINGS_FIELD:
                continue
            for keyword in call.keywords:
                if keyword.arg == SETTINGS_ALIAS and (alias := text(keyword.value, {})):
                    named[declared[0]] = alias
    if len(named) < MIN_ALIASES:
        msg = (
            f"{TIER_MODULE} declares no {SETTINGS_CLASS} field naming an environment variable, so "
            "no tier could be said to serve subagents or not"
        )
        raise HostedTierError(msg)
    return named


def tier_artifacts(call: ast.Call, named: Mapping[str, str]) -> tuple[tuple[str, str], ...]:
    """Every settings field one tier reads its artifact path from, and the variable each names."""
    fields = [
        node.attr
        for keyword in call.keywords
        if keyword.arg == TIER_PATH
        for node in ast.walk(keyword.value)
        if isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == SELF
        and node.attr in named
    ]
    if not fields:
        msg = (
            f"the {TIER_CLASS} at line {call.lineno} names no {SETTINGS_CLASS} field for its "
            f"{TIER_PATH}, so this reader cannot say whether it serves subagents"
        )
        raise HostedTierError(msg)
    return tuple((field, named[field]) for field in fields)


def _serves(call: ast.Call, named: Mapping[str, str]) -> str | None:
    """The variable naming this tier's artifact, when it is a subagent tier's, else None."""
    serving = [
        variable for _, variable in tier_artifacts(call, named) if variable.startswith(MODEL_PREFIX)
    ]
    return serving[0] if serving else None


def _tail(
    call: ast.Call,
    serves: str,
    strings: Mapping[str, str],
    tuples: Mapping[str, tuple[str | None, ...]],
) -> tuple[str, ...]:
    """The flags one subagent tier adds to the shared command, raising when it cannot be read."""
    written = [keyword.value for keyword in call.keywords if keyword.arg == TIER_EXTRA]
    tail = items(written[0], strings, tuples) if written else ()
    if tail is None or any(item is None for item in tail):
        msg = (
            f"the tier under {serves} declares an {TIER_EXTRA} this reader cannot reduce to "
            f"flags; write them as literals or teach {Path(__file__).name} the shape"
        )
        raise HostedTierError(msg)
    return tuple(item for item in tail if item is not None)


def declared(module: ast.Module) -> list[ast.Call]:
    """Every tier the settings module constructs, in the order it writes them."""
    found = [
        node
        for node in ast.walk(module)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == TIER_CLASS
    ]
    if len(found) < MIN_TIERS:
        msg = f"{TIER_MODULE} declares no {TIER_CLASS} at all, so a reading of it cannot fail"
        raise HostedTierError(msg)
    return sorted(found, key=lambda node: node.lineno)


def hosted(root: Path) -> tuple[Tier, ...]:
    """Every tier the model host under ``root`` starts as a subagent, in declaration order."""
    head, tail = shared(parse_module(root, ARGV_MODULE))
    module = parse_module(root, TIER_MODULE)
    named = aliases(module)
    strings, tuples = constants(module)
    found: list[Tier] = []
    for call in declared(module):
        serves = _serves(call, named)
        if serves is None:
            continue
        command = (*head, *_tail(call, serves, strings, tuples), *tail)
        found.append(
            Tier(
                file=(MODEL_MANAGER / TIER_MODULE).as_posix(),
                named=serves,
                line=call.lineno,
                command=tuple(item if item is not None else UNREADABLE for item in command),
            )
        )
    return tuple(found)
