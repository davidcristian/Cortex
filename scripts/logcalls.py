"""What a brain log call really attaches, read out of the module that writes it."""

import ast
import re
from pathlib import Path
from typing import NamedTuple

from skippeddirs import SKIPPED_DIRS

# Where the brain's importable source lives, and the directory each package puts it under. Only
# these trees are walked: a package's tests sit beside `src` rather than inside it, and a logger a
# test declares is not a logger the deployment writes under.
BRAIN_PACKAGES = Path("brain/packages")
SOURCE_DIR = "src"

# How a module claims a logger, in the two spellings the brain uses. `__name__` resolves to the
# module's own dotted path; a literal is the name itself.
GET_LOGGER = re.compile(r"getLogger\(\s*(?:__name__|\"(?P<named>[^\"]+)\")\s*\)")

# The keyword a call attaches its fields under, which is the stdlib's own name for them.
EXTRA = "extra"

# The module name that is a package rather than a module: `cortex_core/__init__.py` is the logger
# `cortex_core` and not `cortex_core.__init__`.
PACKAGE_MODULE = "__init__"

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


def loggers(root: Path) -> dict[str, str]:
    """Every logger name the brain declares, against the repo-relative file that declares it."""
    found: dict[str, str] = {}
    for source in _source_roots(root):
        for module in sorted(source.rglob("*.py")):
            inside = module.relative_to(source)
            if SKIPPED_DIRS & set(inside.parts):
                continue
            shown = module.relative_to(root).as_posix()
            for claim in GET_LOGGER.finditer(_read(module, shown)):
                name = claim["named"] or dotted(inside)
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
    """Why no call was found: because none writes the message, or because one writes it loosely."""
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
    try:
        tree = ast.parse(text)
    except SyntaxError as err:
        msg = f"cannot parse {shown}: {err}"
        raise LogCallError(msg) from err
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
