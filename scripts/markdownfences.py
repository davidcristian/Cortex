"""What a markdown fence is, in the one place every reader here takes the answer from.

Three gates read documents carrying fenced blocks, and each of them used to spell the marker for
itself: `backlogcheck.py` keeps a `#` inside a block from being read as a heading, `samplecheck.py`
reads a log sample inside a block and never out of prose about one, and `commitlint.py` exempts a
fenced paste from the wrap and from the dash ban. Three identical patterns are the shape
`composefiles.py` and `skippeddirs.py` were written to remove: a question several gates ask is
answered once, and the next reader of markdown in this tree starts from that answer.

**How much of the spec this reads, and why no more.** A fence is a marker at the start of a line,
with the indent markdown allows in front of it and an info string after it. The closing rules are
not read: markdown closes a block with a marker of the same character and at least the opening
length, and every reader here toggles on the marker instead. The two readings part company only
where a document nests one block inside another or closes a long fence with a short one, which no
document in this tree does, so the fuller reading would change no answer and would be code written
against text nobody writes.

**The second half of this module is what keeps the first from being copied again.**
`spelled(module)` reports every line where a fence marker is written into a module's code, which is
what the obligation beside it holds this tree to. A marker inside a docstring is prose about a
fence and decides nothing, so a constant standing alone as a statement is passed over; every other
literal carrying a marker is this module's work being done somewhere else. A module that had to
print a fence rather than recognize one would be reported too, which is a fault a reader looks at
rather than a second answer nobody hears about.
"""

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
