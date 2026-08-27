"""What a Python module's own top level binds, read out of its source rather than by importing it.
"""

import ast
from collections.abc import Mapping
from pathlib import Path


class ModuleReadError(Exception):
    """One module cannot be read as Python at all: it is absent, is not text, or does not parse."""


def parse(path: Path, shown: str) -> ast.Module:
    """Parse one module, naming it as ``shown`` when it cannot be read or is not Python."""
    try:
        return ast.parse(path.read_text(encoding="utf-8"), filename=shown)
    except (OSError, UnicodeDecodeError, SyntaxError) as err:
        msg = f"cannot read {shown}: {err}"
        raise ModuleReadError(msg) from err


def text(node: ast.expr, strings: Mapping[str, str]) -> str | None:
    """The string one expression reduces to, or None where this reader cannot say."""
    if isinstance(node, ast.Constant):
        return node.value if isinstance(node.value, str) else None
    if isinstance(node, ast.Name):
        return strings.get(node.id)
    return None


def items(
    node: ast.expr,
    strings: Mapping[str, str],
    tuples: Mapping[str, tuple[str | None, ...]],
) -> tuple[str | None, ...] | None:
    """The run of strings one expression reduces to, or None where it is not a run at all."""
    if isinstance(node, ast.Tuple):
        return tuple(text(item, strings) for item in node.elts)
    if isinstance(node, ast.Name):
        return tuples.get(node.id)
    return None


def bound(statement: ast.stmt) -> tuple[str, ast.expr] | None:
    """The name one statement binds and the expression it binds it to, or None for the rest.

    Both spellings a declaration takes here: a plain assignment, and an annotated one, which is
    how a settings field is written. An annotated declaration with no value binds nothing.
    """
    if isinstance(statement, ast.Assign) and len(statement.targets) == 1:
        target = statement.targets[0]
        return (target.id, statement.value) if isinstance(target, ast.Name) else None
    if isinstance(statement, ast.AnnAssign) and statement.value is not None:
        annotated = statement.target
        return (annotated.id, statement.value) if isinstance(annotated, ast.Name) else None
    return None


def constants(module: ast.Module) -> tuple[dict[str, str], dict[str, tuple[str | None, ...]]]:
    """Every top-level string and run of strings the module binds, by the name it binds it under.

    The two answers come back separately because they are asked separately: a caller wanting a
    flag wants the first, and one wanting a tier's tail wants the second.
    """
    strings: dict[str, str] = {}
    tuples: dict[str, tuple[str | None, ...]] = {}
    for statement in module.body:
        declared = bound(statement)
        if declared is None:
            continue
        name, value = declared
        if (only := text(value, strings)) is not None:
            strings[name] = only
        elif (run := items(value, strings, tuples)) is not None:
            tuples[name] = run
    return strings, tuples
