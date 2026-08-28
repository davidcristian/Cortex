"""What a brain log call really attaches, read out of the module that writes it.

`samplecheck.py`'s code side, and the half a documented sample has never been compared against.
This module answers two questions about the brain's source and nothing else: which module owns a
logger name, and what one call under that logger puts on its line. `logsamples.py` is the doc side,
and the gate holds the two answers together.

**Parsed, not matched.** Every other scan in `scripts/` reads Python as text, which is the right
reflex when the question is a declaration on one line. An ``extra=`` dict is not one line: the
failed-settle call spreads its three keys over five, and a brace counter written to follow that is
a Python parser with the corners missing. ``ast`` parses the same text and executes none of it, so
this reads the brain the way the rest of this tree does, without importing it. The seam the ADR
declined to open is an import of the brain from `scripts/`, and that stays shut.

**A logger name resolves to a file rather than to a package.** ``getLogger(__name__)`` is the
brain's usual spelling, and its answer is the module's own dotted path, which is exactly what a
sample prints between the level and the message. Two sinks name themselves instead, the recall
trail and the tool audit, because their lines are read as a trail rather than as one module's
account of itself. Every spelling is collected, so a sample naming any of them resolves, and a
logger name claimed by two files is a fault rather than a coin toss. A literal written inside the
call is read too, and is the one spelling no module here writes any more: it stays because such a
call is legal Python and a reader that stopped matching one would lose that logger in silence.

**A sink may bind its name above the call, and that is the third spelling.** A self-named logger
restated by documents is declared as a module constant so the constant registry can tie those
documents to it, which both of these sinks now are, and a reader that only knew a literal would
drop such a logger out of this answer the day it was named: the sample quoting it would then fail as
a logger no module declares, which is loud and points at the document rather than at the reader.
So a bare identifier is resolved against that module's own top level, by ``moduleconstants.py``,
which is the same reading `hostedtiers.py` makes of the sidecar's declarations. Nothing wider is
followed. A name imported from another module is refused rather than chased, an importer of the
brain being exactly what this tree may not become.

**A module may not spell one logger name twice.** A declaration is what the constant registry ties
the documents restating a name to, and a literal beside one holds two names where there was one:
move the literal alone and those documents go on being tied to a name the brain no longer writes,
every gate green. So a literal is refused when this module's own top level binds it. Nothing is
asked about how a declaration is spelled, so the rule needs no convention to run over, and a literal
in a module that binds nothing is left alone, being the legal Python the spelling above is read for.

**The level comes from the method, and ``exception`` is an error.** A sample prints the level the
formatter wrote, so the call's own method is what it has to agree with. ``exception`` is the one
name that is not its own level: it logs at ``ERROR`` and adds a traceback, which is why a runbook
quoting one of those lines prints ``ERROR`` and would otherwise look wrong.

**Fields come back in the order the line will print them**, which is name order rather than the
order the call site wrote. That is not this module rearranging the answer: ``render_fields`` sorts,
deliberately, so two lines of one kind stay comparable column by column, and the printed order is
therefore a function of the key set alone. Returning the printed order is what lets one comparison
hold a sample's membership and its order at once, and it is why a sample that permutes its fields
is caught here as well as by the neighbouring-field anchor in the constant registry.

**A line whose level is chosen while the program runs is refused by name.** ``logger.log(level,
message, ...)`` takes its level from a variable, which the model host's request failure really
does, so there is no method name to read one from and no level a sample could be held to. That is
reported as what it is rather than as a message nothing logs, because the message is in the module
and a fault denying it would send a reader looking for text they can see.

**A call this reader cannot account for is a fault**, never a skip: a message no call logs, a
message logged in two places, an ``extra=`` that is not a literal mapping, and a key that is not a
plain string are each reported. A reader that shrugged at one of them would hand the gate an empty
answer and call the document right.
"""

import ast
import re
from pathlib import Path
from typing import NamedTuple

from moduleconstants import constants
from skippeddirs import SKIPPED_DIRS

# Where the brain's importable source lives, and the directory each package puts it under. Only
# these trees are walked: a package's tests sit beside `src` rather than inside it, and a logger a
# test declares is not a logger the deployment writes under.
BRAIN_PACKAGES = Path("brain/packages")
SOURCE_DIR = "src"

# How a module claims a logger, in the three spellings the brain uses. `__name__` resolves to the
# module's own dotted path; a literal is the name itself; and a bare identifier is a name the same
# module bound above the call, which is how a sink whose logger is restated by documents declares
# it for the constant registry to tie them to.
GET_LOGGER = re.compile(
    r"getLogger\(\s*(?:__name__|\"(?P<named>[^\"]+)\"|(?P<bound>[A-Za-z_]\w*))\s*\)"
)

# The keyword a call attaches its fields under, which is the stdlib's own name for them.
EXTRA = "extra"

# The module name that is a package rather than a module: `cortex_core/__init__.py` is the logger
# `cortex_core` and not `cortex_core.__init__`.
PACKAGE_MODULE = "__init__"

# The one logging method whose level is an argument rather than its own name, and where its
# message sits when it is. The model host switches between a warning and an error that way, and a
# line written through it has no level a sample could be held to, so it is refused BY NAME rather
# than reported as a message nothing logs: the message really is in the module, and a fault saying
# otherwise would send a reader looking for text they can see.
DYNAMIC_LEVEL = "log"
DYNAMIC_MESSAGE = 1

# What each logging method prints as its level. `exception` is the one that is not its own name:
# it logs at ERROR with a traceback attached, so a runbook quoting one prints ERROR.
LEVELS = {
    "debug": "DEBUG",
    "info": "INFO",
    "warning": "WARNING",
    "error": "ERROR",
    "exception": "ERROR",
    "critical": "CRITICAL",
}


class LogCallError(Exception):
    """The brain's source could not be read, or a message could not be accounted for in it."""


class LogCall(NamedTuple):
    """One call's contribution to a line: where it stands, its level, and what it will print.

    ``fields`` is in the order the formatter prints them rather than the order the call wrote
    them, name order being what ``render_fields`` sorts to.
    """

    line: int
    level: str
    fields: tuple[str, ...]


def _read(path: Path, shown: str) -> str:
    """Read one brain source file, refusing one that is absent or is not text."""
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as err:
        msg = f"cannot read {shown}: {err}"
        raise LogCallError(msg) from err


def _source_roots(root: Path) -> list[Path]:
    """Every package's `src` directory, in a fixed order so a fault reads the same twice."""
    packages = root / BRAIN_PACKAGES
    try:
        candidates = sorted(packages.iterdir())
    except OSError as err:
        msg = f"cannot read {BRAIN_PACKAGES.as_posix()}: {err}"
        raise LogCallError(msg) from err
    return [package / SOURCE_DIR for package in candidates if (package / SOURCE_DIR).is_dir()]


def dotted(relative: Path) -> str:
    """The dotted name `__name__` holds for a module at ``relative`` inside its source root."""
    parts = relative.with_suffix("").parts
    if parts[-1] == PACKAGE_MODULE:
        parts = parts[:-1]
    return ".".join(parts)


def _parsed(text: str, shown: str) -> ast.Module:
    """Parse one brain module, naming it when what it holds is not Python at all."""
    try:
        return ast.parse(text)
    except SyntaxError as err:
        msg = f"cannot parse {shown}: {err}"
        raise LogCallError(msg) from err


def _literal(named: str, text: str, shown: str) -> str:
    """The name a literal call claims, refused when the same module also binds it.

    Only the binding is what the constant registry ties documents to, so a module holding both
    spellings can move the literal alone and leave them restating a name nothing writes through.
    """
    strings, _ = constants(_parsed(text, shown))
    declared = sorted(name for name, value in strings.items() if value == named)
    if declared:
        msg = (
            f"{shown} writes the logger {named!r} inside the call and binds it above as "
            f"{', '.join(declared)}; pass the binding, so the name is written once"
        )
        raise LogCallError(msg)
    return named


def claimed(claim: re.Match[str], text: str, inside: Path, shown: str) -> str:
    """The logger name one ``getLogger`` call claims, in whichever spelling it claims it.

    A bare identifier is resolved against the module's own top level and nothing wider: a name
    imported from elsewhere is refused rather than followed, since following one would make this
    reader an importer of the brain, which is the seam the architecture keeps shut.
    """
    named = claim["named"]
    if named is not None:
        return _literal(named, text, shown)
    bound = claim["bound"]
    if bound is None:
        return dotted(inside)
    strings, _ = constants(_parsed(text, shown))
    resolved = strings.get(bound)
    if resolved is None:
        msg = f"{shown} names its logger {bound}, which its own top level binds to no string"
        raise LogCallError(msg)
    return resolved


def loggers(root: Path) -> dict[str, str]:
    """Every logger name the brain declares, against the repo-relative file that declares it."""
    found: dict[str, str] = {}
    for source in _source_roots(root):
        for module in sorted(source.rglob("*.py")):
            inside = module.relative_to(source)
            if SKIPPED_DIRS & set(inside.parts):
                continue
            shown = module.relative_to(root).as_posix()
            text = _read(module, shown)
            for claim in GET_LOGGER.finditer(text):
                name = claimed(claim, text, inside, shown)
                if name in found:
                    msg = f"{shown} and {found[name]} both declare the logger {name!r}"
                    raise LogCallError(msg)
                found[name] = shown
    return found


def _keys(call: ast.Call, shown: str) -> tuple[str, ...]:
    """The field names one call attaches, in the order the formatter will print them."""
    for keyword in call.keywords:
        if keyword.arg != EXTRA:
            continue
        if not isinstance(keyword.value, ast.Dict):
            msg = f"{shown}:{call.lineno}: extra= is not a mapping written out at the call"
            raise LogCallError(msg)
        names: list[str] = []
        for key in keyword.value.keys:
            if not isinstance(key, ast.Constant) or not isinstance(key.value, str):
                msg = f"{shown}:{call.lineno}: a field name here is not a plain string"
                raise LogCallError(msg)
            names.append(key.value)
        return tuple(sorted(names))
    return ()


def _message_call(node: ast.AST, message: str) -> tuple[ast.Call, str] | None:
    """``node`` and the level it prints, when it is a logging call carrying exactly ``message``.

    The level is read here rather than by the caller so that the one place which knows the node
    is an attribute call is the one place that spends that knowledge.
    """
    if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
        return None
    level = LEVELS.get(node.func.attr)
    if level is None or not node.args:
        return None
    first = node.args[0]
    if not isinstance(first, ast.Constant) or not isinstance(first.value, str):
        return None
    return (node, level) if first.value == message else None


def _dynamic_call(node: ast.AST, message: str) -> ast.Call | None:
    """``node`` when it logs ``message`` at a level chosen while the program runs."""
    if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
        return None
    if node.func.attr != DYNAMIC_LEVEL or len(node.args) <= DYNAMIC_MESSAGE:
        return None
    written = node.args[DYNAMIC_MESSAGE]
    if not isinstance(written, ast.Constant) or not isinstance(written.value, str):
        return None
    return node if written.value == message else None


def _absent(tree: ast.Module, message: str, shown: str) -> str:
    """Why no call was found: because none writes the message, or because one writes it loosely.

    The second answer costs one more walk and saves the reader the whole investigation. A line
    written through ``log`` really is in the module, and a fault saying it is not would send
    somebody looking for a message they can see with their own eyes.
    """
    for node in ast.walk(tree):
        call = _dynamic_call(node, message)
        if call is not None:
            return (
                f"{shown}:{call.lineno} logs {message!r} at a level chosen while it runs, "
                "which is not a level a sample can state"
            )
    return f"{shown} logs no message {message!r}"


def logged(text: str, message: str, shown: str) -> LogCall:
    """The one call in ``text`` that logs ``message``, or a fault naming what was found instead."""
    tree = _parsed(text, shown)
    found = [call for node in ast.walk(tree) if (call := _message_call(node, message)) is not None]
    if not found:
        raise LogCallError(_absent(tree, message, shown))
    if len(found) > 1:
        calls = sorted(found, key=lambda pair: pair[0].lineno)
        lines = ", ".join(str(call.lineno) for call, _ in calls)
        msg = f"{shown} logs {message!r} in {len(found)} places (lines {lines})"
        raise LogCallError(msg)
    call, level = found[0]
    return LogCall(line=call.lineno, level=level, fields=_keys(call, shown))
