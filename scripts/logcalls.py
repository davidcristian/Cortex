"""What a brain log call really attaches, read out of the module that writes it."""

import ast
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import NamedTuple

from logfields import FieldError, attached
from moduleconstants import constants, text
from treewalk import walk_files

# Where the brain's importable source lives, and the directory each package puts it under. Only
# these trees are walked: a package's tests sit beside `src` rather than inside it, and a logger a
# test declares is not a logger the deployment writes under.
BRAIN_PACKAGES = Path("brain/packages")
SOURCE_DIR = "src"
PYTHON = ".py"

# The one logging method whose level is an argument rather than its own name, and where its
# message sits when it is. The model host switches between a warning and an error that way, and a
# line written through it has no level a sample could be held to.
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


class UnreadFieldsError(LogCallError):
    """A call was found and its level read, and its field list cannot be read off the source."""

    def __init__(self, line: int, level: str, reason: str) -> None:
        super().__init__(reason)
        self.line = line
        self.level = level
        self.reason = reason


class LogCall(NamedTuple):
    """One call's contribution to a line: where it stands, its level, and what it will print.

    ``fields`` is in the order the formatter prints them rather than the order the call wrote
    them, name order being what ``render_fields`` sorts to.
    """

    line: int
    level: str
    fields: tuple[str, ...]


def read(path: Path, shown: str) -> str:
    """Read one brain source file, raising when it is absent or is not text."""
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
        for module in sorted(walk_files(source)):
            if module.suffix == PYTHON:
                yield module, module.relative_to(source), module.relative_to(root).as_posix()


def parsed(source: str, shown: str) -> ast.Module:
    """Parse one brain module, naming it when what it holds is not Python at all."""
    try:
        return ast.parse(source)
    except SyntaxError as err:
        msg = f"cannot parse {shown}: {err}"
        raise LogCallError(msg) from err


def _written(first: ast.expr, strings: Mapping[str, str], shown: str, at: int) -> str | None:
    """The message one call carries, in either spelling, or None where this reader cannot say."""
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


def _logs(node: ast.AST) -> bool:
    """Whether ``node`` is such a call, which is the rule the field reader is handed."""
    return _levelled(node) is not None


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


def handed(tree: ast.Module) -> list[tuple[int, str]]:
    """Every logging call whose message is a bare name: the line the name is on, and the name."""
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        levelled = _levelled(node)
        if levelled is None:
            continue
        first = levelled[0].args[0]
        if isinstance(first, ast.Name):
            found.append((first.lineno, first.id))
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
    """Why no call was found: because none writes the message, or because one writes it loosely."""
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
    try:
        fields = attached(call, tree, shown, is_log_call=_logs)
    except FieldError as err:
        raise UnreadFieldsError(call.lineno, level, str(err)) from err
    return LogCall(line=call.lineno, level=level, fields=fields)


def messages(root: Path) -> dict[str, tuple[str, ...]]:
    """Every message the brain logs, against the repo-relative file whose calls carry it."""
    found: dict[str, tuple[str, ...]] = {}
    for module, _, shown in modules(root):
        tree = parsed(read(module, shown), shown)
        written = {message for _, _, message in carried(tree, shown)}
        if written:
            found[shown] = tuple(sorted(written))
    return found
