"""What a markdown fence is, defined once for every reader here."""

import ast

MARKERS = ("```", "~~~")

CHARACTERS = frozenset(marker[0] for marker in MARKERS)
LEAST = min(len(marker) for marker in MARKERS)


def _marker(line: str) -> str | None:
    """The run of fence characters ``line`` opens with, or None where it opens with none."""
    text = line.lstrip()
    if not text or text[0] not in CHARACTERS:
        return None
    run = len(text) - len(text.lstrip(text[0]))
    return text[:run] if run >= LEAST else None


class Fences:
    """Where a document's fenced blocks stand, read one line at a time in document order."""

    def __init__(self) -> None:
        self._opened = ""

    @property
    def inside(self) -> bool:
        """Whether the lines read so far leave a block open."""
        return bool(self._opened)

    def _closes(self, marker: str) -> bool:
        """Whether one marker closes the block now open."""
        return marker[0] == self._opened[0] and len(marker) >= len(self._opened)

    def closes(self, line: str) -> bool:
        """Whether ``line`` closes the block now open, leaving the reading where it was."""
        marker = _marker(line)
        return marker is not None and self.inside and self._closes(marker)

    def bounds(self, line: str) -> bool:
        """Whether ``line`` opens or closes a block, reading it into the state."""
        marker = _marker(line)
        if marker is None:
            return False
        if not self.inside:
            self._opened = marker
            return True
        if self._closes(marker):
            self._opened = ""
            return True
        return False


def _prose(module: ast.Module) -> frozenset[int]:
    """Every docstring in ``module``, by identity: a string literal alone as a statement."""
    return frozenset(
        id(node.value)
        for node in ast.walk(module)
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant)
    )


def _marked(node: ast.Constant, prose: frozenset[int]) -> bool:
    """Whether one literal is a string with a fence marker in it and is not a docstring."""
    return (
        isinstance(node.value, str)
        and id(node) not in prose
        and any(marker in node.value for marker in MARKERS)
    )


def marker_lines(module: ast.Module) -> list[int]:
    """Every line of ``module`` where a fence marker is written into code, in line order."""
    prose = _prose(module)
    return sorted(
        node.lineno
        for node in ast.walk(module)
        if isinstance(node, ast.Constant) and _marked(node, prose)
    )
