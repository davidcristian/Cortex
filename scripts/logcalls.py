"""What a brain log call really attaches, read out of the module that writes it.

`samplecheck.py`'s code side, and the half a documented sample has never been compared against.
This module answers what one call puts on its line, and holds the reading of the brain's source
that `loggernames.py` answers the other half over: which module owns the logger a line is written
through. `logsamples.py` is the doc side, and the gate holds the two answers together.

**Parsed, not matched.** Every other scan in `scripts/` reads Python as text, which is the right
reflex when the question is a declaration on one line. An ``extra=`` dict is not one line: the
failed-settle call spreads its three keys over five, and a brace counter written to follow that is
a Python parser with the corners missing. ``ast`` parses the same text and executes none of it, so
this reads the brain the way the rest of this tree does, without importing it. The seam the ADR
declined to open is an import of the brain from `scripts/`, and that stays shut.

**A message is written out at the call, or handed to it by name.** Both spellings print the same
line, the formatter rendering the string and never the expression that carried it, so a document
quoting one cannot tell which the module wrote. A reader that knew only a literal therefore said
that a sink handing its call a constant logs no such message, which is a fault about the document
where the code is the thing that moved, and it fell on exactly the sinks a runbook has most reason
to quote. So a bare identifier is resolved against the module's own top level and nothing wider, by
``moduleconstants.py``, which is the reading `loggernames.py` next door already makes of a logger
claimed the same way. A name from anywhere else stays unmatched rather than chased, an importer of
the brain being what this tree may not become, and a message built at the call out of pieces is not
a message a page could quote at all.

**A module may not spell one message twice.** This is the one-name rule beside it one word over,
and the same sentence: a declaration is what the constant registry ties the documents restating a
message to, and a literal of the same string in the call holds two words where there was one, so
the day the literal moves alone those documents go on restating a word the brain no longer writes,
every gate green. So a literal message is refused when this module's own top level binds it. The
domain is a call and not a name, which is what keeps the rule off a module that binds some string
for another purpose: the string has to be the message of a log call here before anything is asked
about it, and then the module has two spellings of one word whatever the binding was written for.

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
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import NamedTuple

from moduleconstants import constants, text
from skippeddirs import SKIPPED_DIRS

# Where the brain's importable source lives, and the directory each package puts it under. Only
# these trees are walked: a package's tests sit beside `src` rather than inside it, and a logger a
# test declares is not a logger the deployment writes under.
BRAIN_PACKAGES = Path("brain/packages")
SOURCE_DIR = "src"

# The keyword a call attaches its fields under, which is the stdlib's own name for them.
EXTRA = "extra"

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


def read(path: Path, shown: str) -> str:
    """Read one brain source file, refusing one that is absent or is not text."""
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as err:
        msg = f"cannot read {shown}: {err}"
        raise LogCallError(msg) from err


def modules(root: Path) -> Iterator[tuple[Path, Path, str]]:
    """Every brain source module: the file, its path inside its source root, and how to name it.

    One walk for both halves of this reader, in a fixed order so a fault reads the same twice.
    """
    packages = root / BRAIN_PACKAGES
    try:
        candidates = sorted(packages.iterdir())
    except OSError as err:
        msg = f"cannot read {BRAIN_PACKAGES.as_posix()}: {err}"
        raise LogCallError(msg) from err
    for package in candidates:
        source = package / SOURCE_DIR
        if not source.is_dir():
            continue
        for module in sorted(source.rglob("*.py")):
            inside = module.relative_to(source)
            if not SKIPPED_DIRS & set(inside.parts):
                yield module, inside, module.relative_to(root).as_posix()


def parsed(source: str, shown: str) -> ast.Module:
    """Parse one brain module, naming it when what it holds is not Python at all."""
    try:
        return ast.parse(source)
    except SyntaxError as err:
        msg = f"cannot parse {shown}: {err}"
        raise LogCallError(msg) from err


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


def _written(first: ast.expr, strings: Mapping[str, str], shown: str, at: int) -> str | None:
    """The message one call carries, in either spelling, or None where this reader cannot say.

    A literal is refused when the same module also binds it, for the reason the module docstring
    gives; a name is whatever that module's own top level binds it to, and nothing when the name
    comes from anywhere else.
    """
    message = text(first, strings)
    if message is None or isinstance(first, ast.Name):
        return message
    declared = sorted(name for name, value in strings.items() if value == message)
    if declared:
        msg = (
            f"{shown}:{at} writes the message {message!r} inside the call and binds it above as "
            f"{', '.join(declared)}; pass the binding, so the word is written once"
        )
        raise LogCallError(msg)
    return message


def _levelled(node: ast.AST) -> tuple[ast.Call, str] | None:
    """``node`` and the level it prints, when it is a logging call at a level of its own name."""
    if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
        return None
    level = LEVELS.get(node.func.attr)
    return (node, level) if level is not None and node.args else None


def carried(tree: ast.Module, shown: str) -> list[tuple[ast.Call, str, str]]:
    """Every logging call in one module, with the level it prints and the message it carries."""
    strings, _ = constants(tree)
    found: list[tuple[ast.Call, str, str]] = []
    for node in ast.walk(tree):
        levelled = _levelled(node)
        if levelled is None:
            continue
        call, level = levelled
        message = _written(call.args[0], strings, shown, call.lineno)
        if message is not None:
            found.append((call, level, message))
    return found


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


def logged(source: str, message: str, shown: str) -> LogCall:
    """The one call in ``source`` that logs ``message``, or a fault naming what was found."""
    tree = parsed(source, shown)
    found = [(call, level) for call, level, written in carried(tree, shown) if written == message]
    if not found:
        raise LogCallError(_absent(tree, message, shown))
    if len(found) > 1:
        lines = ", ".join(str(call.lineno) for call, _ in sorted(found, key=lambda p: p[0].lineno))
        msg = f"{shown} logs {message!r} in {len(found)} places (lines {lines})"
        raise LogCallError(msg)
    call, level = found[0]
    return LogCall(line=call.lineno, level=level, fields=_keys(call, shown))


def messages(root: Path) -> dict[str, tuple[str, ...]]:
    """Every message the brain logs, against the repo-relative file whose calls carry it.

    The reading the one-message rule runs over: a module is asked for its calls whether or not any
    document quotes one, so a word spelled twice is refused the day it is written rather than the
    day a runbook prints it.
    """
    found: dict[str, tuple[str, ...]] = {}
    for module, _, shown in modules(root):
        tree = parsed(read(module, shown), shown)
        written = {message for _, _, message in carried(tree, shown)}
        if written:
            found[shown] = tuple(sorted(written))
    return found
