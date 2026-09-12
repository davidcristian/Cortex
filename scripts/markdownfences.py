"""What a markdown fence is, in the one place every reader here takes the answer from."""

import ast
import re

# The two markers markdown accepts for a fenced block, three of either character. They are spelled
# here and nowhere else: the pattern below is built from them, and `spelled` searches for them.
MARKERS = ("```", "~~~")

# A fence: the indent markdown allows, then a marker. Neither marker carries a regex
# metacharacter, so both go into the pattern exactly as they are written above.
FENCE = re.compile(rf"^\s*(?:{'|'.join(MARKERS)})")


def is_fence(line: str) -> bool:
    """Whether ``line`` opens or closes a fenced block."""
    return FENCE.match(line) is not None


def _prose(module: ast.Module) -> frozenset[int]:
    """Every docstring in ``module``, by identity: a constant standing alone as a statement.

    Identity rather than text, since two docstrings quoting the same fence are two nodes and only
    the one being looked at is the one to pass over.
    """
    return frozenset(
        id(node.value)
        for node in ast.walk(module)
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant)
    )


def _marked(node: ast.Constant, prose: frozenset[int]) -> bool:
    """Whether one literal is a string carrying a fence marker and is not a docstring."""
    return (
        isinstance(node.value, str)
        and id(node) not in prose
        and any(marker in node.value for marker in MARKERS)
    )


def spelled(module: ast.Module) -> list[int]:
    """Every line of ``module`` where a fence marker is written into code, in line order."""
    prose = _prose(module)
    return sorted(
        node.lineno
        for node in ast.walk(module)
        if isinstance(node, ast.Constant) and _marked(node, prose)
    )
