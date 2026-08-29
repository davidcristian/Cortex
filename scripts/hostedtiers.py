"""Which tiers the model host starts as subagents, read off the sidecar's own declaration.

`flagcheck.py` owns the rule and this module owns the second of the two sets it is applied to.
`subagentservers.py` answers for the servers a composed stack starts, which is every subagent
server whose argv is written in a compose file. The one that is not is the model host's own hosted
subagent tier: the supervisor starts it as a child process, and its argv is assembled in Python
from a `TierArgs` the settings module declares. That placement was outside the rule and correct by
hand, one position in a fixed tuple, so a fourth tier added for a second subagent pick would have
carried whatever its author copied while the rule went on holding the compose servers.

**One rule, two readers, and a reader is not the claim.** What a subagent server must be started
with stays written once, in `flagcheck.REQUIREMENTS`. This module adds members and not a second
requirement, which is the whole difference between a second reader and a second way to write one
claim: a fourth flag added to the rule reaches this tier the day it is written, and a flag renamed
on either side reddens, because the sidecar's own `_JINJA` and `_REASONING_OFF` are now compared
against the rule rather than each trusted to a reader of its own.

**A tier serves subagents when the setting naming its artifact does**, which is the reading the
compose side already makes. There the argv spends a `CORTEX_MODEL_FILE_SUBAGENT*` variable; here
the settings field holding the tier's model path carries one as its `validation_alias`, and
`MODEL_PREFIX` is the single place that prefix is written. The tier's logical id is deliberately
not the test: an id is what a deployment renames, and this question must keep its answer under one.

**That reading rests on a naming convention, so the same declaration is read a second way.**
`tier_artifacts` returns every tier's artifact variable with no filter at all, which is what
`artifactnames.py` joins to the compose side and `flagcheck.py` holds to the family prefix: a
tier whose artifact is spelled outside it would otherwise leave this set in silence. The two
readings share one walk of the declaration rather than being two readers of it.

**The flags are read out of the argv builder rather than restated here.** Every tier's command is
the fixed run of items that builder returns with the tier's own `extra` splatted into it, so this
reads that return tuple, resolves what it can, and splices the tail in at the splat. Nothing about
which flags matter is written in this module, which is what keeps the rule single.

**An item this reader cannot reduce to a string becomes a token no requirement can be met by.**
A port rendered with `str()` is a value rather than a flag and nothing compares it, but dropping
it would close the gap between a flag and the item after it, and a check reading the wrong
neighbour is worse than one reporting an item it cannot see. So an unreadable item is `UNREADABLE`
and the gate fails closed on it.

**A subagent tier's own tail is refused rather than approximated.** That tail is the whole of what
one tier adds to the shared command, so a shape this reader was not taught (a call, a splat, a
value assembled while the program runs) is reported by name rather than filled with a token whose
fault message would send a reader hunting for a flag they can see written down. Everything else it
was not taught leaves by the same door: an absent module, a builder whose return it cannot read, a
settings class declaring no environment names, a tree declaring no tier at all, and a tier whose
artifact path names no setting this reader can resolve.
"""

import ast
from collections.abc import Mapping
from pathlib import Path
from typing import NamedTuple

from moduleconstants import ModuleReadError, bound, constants, items, parse, text
from subagentservers import MODEL_PREFIX

# Where the sidecar declares its tiers: the module assembling one tier's argv, and the module
# declaring which tiers there are and what each of them adds to that argv.
MODEL_MANAGER = Path("brain/packages/model_manager/src/cortex_model_manager")
ARGV_MODULE = "tiers.py"
TIER_MODULE = "config.py"

# What is read out of the two. The builder every tier's command comes from and the splat a tier's
# own tail rides on; the settings class, the dataclass a tier is declared as, the keyword carrying
# the artifact path that says which setting a tier belongs to, and the keyword carrying its tail.
ARGV_FUNCTION = "llama_server_argv"
TIER_CLASS = "TierArgs"
TIER_EXTRA = "extra"
TIER_PATH = "model_path"
SETTINGS_CLASS = "ModelHostConfig"
SETTINGS_FIELD = "Field"
SETTINGS_ALIAS = "validation_alias"
SELF = "self"

# An argv item this reader cannot reduce to a string. It is spelled so that no flag name and no
# required value can ever equal it, its whole job being to occupy a position without satisfying
# anything a rule might require at one.
UNREADABLE = "<computed>"

# A tree declaring no tier at all, or a settings class naming no environment variable, is a
# reading that would answer emptily forever rather than one with nothing to say.
MIN_TIERS = 1
MIN_ALIASES = 1


class HostedTierError(Exception):
    """The sidecar's tier declarations cannot be read, or say something this reader cannot."""


class Tier(NamedTuple):
    """One hosted tier serving subagents, and the command the supervisor would start it with.

    ``named`` is the environment variable a deployment names the tier's artifact under, which is
    both what makes it one of these and the word an operator would recognise it by; a logical id
    is renameable and would name a different thing to different deployments.
    """

    file: str
    named: str
    line: int
    command: tuple[str, ...]


def parse_module(root: Path, name: str) -> ast.Module:
    """One of the sidecar's modules, with the syntax reader's refusal carried out this door."""
    try:
        return parse(root / MODEL_MANAGER / name, (MODEL_MANAGER / name).as_posix())
    except ModuleReadError as err:
        raise HostedTierError(str(err)) from err


def _returned(module: ast.Module) -> ast.Tuple:
    """The tuple the argv builder returns, refusing a shape this reader cannot splice into.

    Exactly one return, because a builder that returns one argv down one branch and another down
    a second is a builder whose flags depend on something this reader is not evaluating, and
    reading the first would be a gate green over the branch it did not take.
    """
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
    """What every tier's command carries before and after its own tail.

    The splat is found rather than assumed: exactly one is expected and it must be the tier's own
    ``extra``, since a second one would leave nowhere to put the tail and a different one would
    mean the tail no longer lands where this reader puts it.
    """
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
            "cannot say where a tier's own flags land in its command"
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
    """Every settings field one tier reads its artifact path from, and the variable each names.

    Unfiltered, because the question above this one is whether every artifact this tree names is
    named so that a reader can classify it at all, and an artifact spelled outside the family is
    exactly the one a subagent filter here would drop. `_serves` applies that filter; the naming
    rule in `flagcheck.py` reads this.
    """
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
    """The flags one subagent tier adds to the shared command, refused when it cannot be read."""
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
