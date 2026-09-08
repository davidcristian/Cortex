"""What a module under `scripts/` calls, read from its syntax rather than from its text."""

import ast
from typing import NamedTuple

DESCENDS = frozenset({"walk", "rglob"})
PATTERNED = frozenset({"glob", "iglob"})
DEEP = "**"
SYNTAX = "ast"
GIT = "git"
ENV = "env"


class Read(NamedTuple):
    """One call that descends a directory tree: the line it is on and the function it names."""

    line: int
    called: str


class GitCall(NamedTuple):
    """One call handed a git argv, and the function its `env=` keyword calls, if it has one."""

    line: int
    environment: str | None


def _named(node: ast.Call) -> str | None:
    """The name of the function one call names, without the module it is written on."""
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    if isinstance(node.func, ast.Name):
        return node.func.id
    return None


def _word(node: ast.expr) -> str | None:
    """The string one expression is written as, or None where it is not a literal string."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _spelled_on(node: ast.Call, module: str) -> bool:
    """Whether the call is written as an attribute of ``module``, as `ast.walk` is."""
    return (
        isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == module
    )


def _listing(node: ast.Call) -> bool:
    """Whether a `glob` names one directory's entries rather than everything below it."""
    if not node.args:
        return False
    pattern = _word(node.args[0])
    return pattern is not None and DEEP not in pattern


def descended(node: ast.Call) -> str | None:
    """The name of the call reading a directory tree, or None where it reads no tree."""
    name = _named(node)
    if name in DESCENDS:
        return None if _spelled_on(node, SYNTAX) else name
    if name in PATTERNED:
        return None if _listing(node) else name
    return None


def tree_reads(module: ast.Module) -> list[Read]:
    """Every call in ``module`` that reads a directory tree, in line order."""
    found = [
        Read(line=node.lineno, called=name)
        for node in ast.walk(module)
        if isinstance(node, ast.Call) and (name := descended(node)) is not None
    ]
    return sorted(found)


def _written(node: ast.expr) -> bool:
    """Whether one expression is a git argv written out: a sequence opening with the word."""
    return isinstance(node, ast.List | ast.Tuple) and bool(node.elts) and _word(node.elts[0]) == GIT


def _argv(node: ast.expr, bound: frozenset[str]) -> bool:
    """Whether one expression is a git argv, written out or named."""
    if isinstance(node, ast.Name):
        return node.id in bound
    return _written(node)


def _assigned(node: ast.AST) -> tuple[list[ast.expr], ast.expr | None]:
    """What one statement assigns and what it assigns to, annotated or not, or nothing."""
    if isinstance(node, ast.Assign):
        return node.targets, node.value
    if isinstance(node, ast.AnnAssign):
        return [node.target], node.value
    return [], None


def _bound(module: ast.Module) -> frozenset[str]:
    """Every name in ``module`` assigned a git argv, so a call handed one is handed the argv."""
    names: set[str] = set()
    for node in ast.walk(module):
        targets, value = _assigned(node)
        if value is not None and _written(value):
            names.update(target.id for target in targets if isinstance(target, ast.Name))
    return frozenset(names)


def _environment(node: ast.Call) -> str | None:
    """The name of the function this call's `env=` keyword calls, or None where it calls none."""
    for keyword in node.keywords:
        if keyword.arg == ENV and isinstance(keyword.value, ast.Call):
            return _named(keyword.value)
    return None


def git_calls(module: ast.Module) -> list[GitCall]:
    """Every call in ``module`` handed a git argv, in line order."""
    bound = _bound(module)
    found = [
        GitCall(line=node.lineno, environment=_environment(node))
        for node in ast.walk(module)
        if isinstance(node, ast.Call) and node.args and _argv(node.args[0], bound)
    ]
    return sorted(found, key=lambda call: call.line)
