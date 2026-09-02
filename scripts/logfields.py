"""The field names one brain log call attaches, read off the call or off the binding above it.

`logcalls.py`'s field half, split off it at the line cap. A call's ``extra=`` is read in three
spellings: a mapping written out at the call, a bare name, and that name unioned with a mapping
written out at the call. A name is followed inside the function the call is written in and no
wider, to one binding at the top of that function's body above the call, and only when nothing
else in the function names it, so the mapping reaching the call is the one written out and no
branch can have grown it. Every other spelling is refused rather than read, because a field list
read off a mapping something else may have changed would hold a document to a line nothing
prints (ADR-0009 composed-fields addendum).
"""

import ast
from collections.abc import Callable, Iterator

from moduleconstants import bound

# The keyword a call attaches its fields under, which is the stdlib's own name for them.
EXTRA = "extra"

# The two statement kinds a call can be written inside. A class body is not a scope of its own
# here: a call at a class's top level is read as the module's, and the brain writes none.
FUNCTIONS = (ast.FunctionDef, ast.AsyncFunctionDef)

Function = ast.FunctionDef | ast.AsyncFunctionDef
Naming = ast.Name | ast.Global | ast.Nonlocal
IsLogCall = Callable[[ast.AST], bool]


class FieldError(Exception):
    """A call's field list cannot be read off its source without guessing."""


def enclosing(tree: ast.Module, call: ast.Call) -> Function | None:
    """The innermost function ``call`` is written in, or None for a call at the module's top level.

    A function nested in another starts on a later line, so of the functions holding the call the
    innermost is the one defined last.
    """
    holding = [
        node
        for node in ast.walk(tree)
        if isinstance(node, FUNCTIONS) and any(inner is call for inner in ast.walk(node))
    ]
    return max(holding, key=lambda function: function.lineno, default=None)


def _literal(mapping: ast.Dict, shown: str) -> list[str]:
    """The keys of one mapping written out, each of which has to be a plain string."""
    names: list[str] = []
    for key in mapping.keys:
        if not isinstance(key, ast.Constant) or not isinstance(key.value, str):
            msg = f"{shown}:{mapping.lineno}: a field name here is not a plain string"
            raise FieldError(msg)
        names.append(key.value)
    return names


def _handed(function: Function, is_log_call: IsLogCall) -> set[int]:
    """Every name a log call in ``function`` is handed as its ``extra=``, bare or unioned, by id."""
    found: set[int] = set()
    for node in ast.walk(function):
        if not isinstance(node, ast.Call) or not is_log_call(node):
            continue
        for keyword in node.keywords:
            if keyword.arg != EXTRA:
                continue
            value = keyword.value
            if isinstance(value, ast.BinOp) and isinstance(value.op, ast.BitOr):
                value = value.left
            if isinstance(value, ast.Name):
                found.add(id(value))
    return found


def _naming(node: ast.AST, name: str, skip: ast.AST) -> Iterator[Naming]:
    """Every node under ``node`` naming ``name``, with ``skip`` and everything under it left out."""
    for child in ast.iter_child_nodes(node):
        if child is skip:
            continue
        if (isinstance(child, ast.Name) and child.id == name) or (
            isinstance(child, (ast.Global, ast.Nonlocal)) and name in child.names
        ):
            yield child
        yield from _naming(child, name, skip)


def _binding(
    function: Function, name: str, call: ast.Call, shown: str
) -> tuple[ast.stmt, ast.Dict]:
    """The one statement at the top of ``function``'s body binding ``name`` above ``call``."""
    found: list[tuple[ast.stmt, ast.expr]] = []
    for statement in function.body:
        declared = bound(statement)
        if declared is not None and declared[0] == name and statement.lineno < call.lineno:
            found.append((statement, declared[1]))
    if len(found) > 1:
        lines = ", ".join(str(statement.lineno) for statement, _ in found)
        msg = (
            f"{shown}:{call.lineno}: extra= names {name}, which the enclosing function binds "
            f"more than once above the call (lines {lines})"
        )
        raise FieldError(msg)
    if len(found) == 1:
        statement, value = found[0]
        if isinstance(value, ast.Dict):
            return statement, value
    msg = (
        f"{shown}:{call.lineno}: extra= names {name}, which the enclosing function does not "
        "bind above the call to a mapping written out"
    )
    raise FieldError(msg)


def _followed(
    function: Function, name: str, call: ast.Call, shown: str, is_log_call: IsLogCall
) -> list[str]:
    """The keys of the mapping ``name`` is bound to above ``call``, once nothing else names it."""
    statement, mapping = _binding(function, name, call, shown)
    handed = _handed(function, is_log_call)
    for node in _naming(function, name, skip=statement):
        if id(node) not in handed:
            msg = (
                f"{shown}:{call.lineno}: extra= names {name}, bound at line {statement.lineno} "
                f"and used again at line {node.lineno}, so the mapping reaching the call is not "
                "the one written out"
            )
            raise FieldError(msg)
    return _literal(mapping, shown)


def _named(
    value: ast.expr, call: ast.Call, tree: ast.Module, shown: str, is_log_call: IsLogCall
) -> list[str]:
    """Every key the ``extra=`` expression ``value`` carries, in any of the three spellings."""
    if isinstance(value, ast.Dict):
        return _literal(value, shown)
    unioned: list[str] = []
    if (
        isinstance(value, ast.BinOp)
        and isinstance(value.op, ast.BitOr)
        and isinstance(value.right, ast.Dict)
    ):
        unioned = _literal(value.right, shown)
        value = value.left
    function = enclosing(tree, call) if isinstance(value, ast.Name) else None
    if not isinstance(value, ast.Name) or function is None:
        msg = (
            f"{shown}:{call.lineno}: extra= is not a mapping written out at the call, nor a name "
            "the enclosing function binds to one"
        )
        raise FieldError(msg)
    return _followed(function, value.id, call, shown, is_log_call) + unioned


def attached(
    call: ast.Call, tree: ast.Module, shown: str, *, is_log_call: IsLogCall
) -> tuple[str, ...]:
    """The field names ``call`` attaches, in the order the formatter will print them.

    ``is_log_call`` says which calls in ``tree`` are log calls: a name handed to one of those as
    its ``extra=`` is a use this reader accounts for, and a name handed to anything else is not.
    """
    for keyword in call.keywords:
        if keyword.arg == EXTRA:
            return tuple(sorted(set(_named(keyword.value, call, tree, shown, is_log_call))))
    return ()
