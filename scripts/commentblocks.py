"""Find comments and docstrings in source text, and count their lines the same way everywhere."""

import ast
import io
import re
import tokenize
from typing import NamedTuple

DIRECTIVES = (
    "noqa",
    "type: ignore",
    "pragma",
    "pyright:",
    "fmt:",
    "ruff:",
    "nosec",
    "@ts-",
    "eslint-",
    "<reference",
    "syntax=",
)
_CODING = re.compile(r"coding[:=]")
_CODING_LINES = 2
_LINE_BREAK = re.compile(r"\r\n?|\n")
_OPENING = re.compile(r"^[rRuUbBfF]*(\"\"\"|'''|\"|')")
_CLOSING = re.compile(r"(\"\"\"|'''|\"|')$")
_LAYOUT = frozenset(
    {
        tokenize.COMMENT,
        tokenize.NL,
        tokenize.NEWLINE,
        tokenize.INDENT,
        tokenize.DEDENT,
        tokenize.ENDMARKER,
        tokenize.ENCODING,
    }
)
_OWNERS = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
_FUNCTIONS = (ast.FunctionDef, ast.AsyncFunctionDef)
_Owner = ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef


class SourceError(Exception):
    """Python source that cannot be tokenized or parsed."""


class CommentLine(NamedTuple):
    """The comment text on one line, with the comment markers removed."""

    line: int
    text: str


class Comments(NamedTuple):
    """Every comment line in a file, and the lines that hold code instead of a comment block."""

    lines: list[CommentLine]
    code: frozenset[int]


class Block(NamedTuple):
    """A comment block: its first and last line, and how many of its lines count."""

    first: int
    last: int
    lines: int


class Docstring(NamedTuple):
    """A Python docstring: its first and last line, and the text of each line without quotes."""

    first: int
    last: int
    text: tuple[str, ...]

    @property
    def lines(self) -> int:
        """The number of lines that hold text."""
        return sum(1 for text in self.text if text.strip())


def is_directive(comment: CommentLine) -> bool:
    """Return True for a comment a tool reads: a shebang, a coding line, or a lint directive."""
    if comment.line == 1 and comment.text.startswith("!"):
        return True
    if comment.line <= _CODING_LINES and _CODING.search(comment.text):
        return True
    return comment.text.strip().startswith(DIRECTIVES)


def counts(comment: CommentLine) -> bool:
    """Return True when a comment line counts toward its block's length."""
    return bool(comment.text.strip()) and not is_directive(comment)


def comment_blocks(comments: Comments) -> list[Block]:
    """Group comment lines into blocks that no code line interrupts, and count each block."""
    blocks: list[Block] = []
    run: list[CommentLine] = []
    for comment in comments.lines:
        if comment.line in comments.code:
            continue
        if run and any(line in comments.code for line in range(run[-1].line, comment.line)):
            blocks.append(_block(run))
            run = []
        run.append(comment)
    if run:
        blocks.append(_block(run))
    return blocks


def _block(run: list[CommentLine]) -> Block:
    return Block(first=run[0].line, last=run[-1].line, lines=sum(map(counts, run)))


def _comment_start(line: str, marker: str) -> int | None:
    quote = ""
    for index, char in enumerate(line):
        if quote:
            quote = "" if char == quote else quote
        elif char in "\"'":
            quote = char
        elif line.startswith(marker, index) and (index == 0 or line[index - 1].isspace()):
            return index
    return None


def hash_comments(text: str, marker: str = "#") -> Comments:
    """Find comments that start with ``marker`` at the start of a line or after whitespace."""
    found: list[CommentLine] = []
    code: set[int] = set()
    for number, line in enumerate(_LINE_BREAK.split(text), start=1):
        start = _comment_start(line, marker)
        before = line if start is None else line[:start]
        if before.strip():
            code.add(number)
        if start is not None:
            found.append(CommentLine(line=number, text=line[start + len(marker) :]))
    return Comments(lines=found, code=frozenset(code))


def python_comments(source: str) -> Comments:
    found: list[CommentLine] = []
    code: set[int] = set()
    try:
        for token in tokenize.generate_tokens(io.StringIO(source).readline):
            if token.type == tokenize.COMMENT:
                found.append(CommentLine(line=token.start[0], text=token.string[1:]))
            elif token.type not in _LAYOUT:
                code.update(range(token.start[0], token.end[0] + 1))
    except (tokenize.TokenError, SyntaxError) as err:
        raise SourceError(str(err)) from err
    return Comments(lines=found, code=frozenset(code))


def _docstring_text(lines: list[str], node: ast.Constant) -> tuple[str, ...]:
    first, last = node.lineno - 1, (node.end_lineno or node.lineno) - 1
    start, end = node.col_offset, node.end_col_offset
    pieces = [line.encode() for line in lines[first : last + 1]]
    pieces[-1] = pieces[-1][:end]
    pieces[0] = pieces[0][start:]
    text = [piece.decode() for piece in pieces]
    text[0] = _OPENING.sub("", text[0].lstrip())
    text[-1] = _CLOSING.sub("", text[-1].rstrip())
    return tuple(text)


def _parse(source: str) -> ast.Module:
    try:
        return ast.parse(source)
    except SyntaxError as err:
        raise SourceError(str(err)) from err


def _docstring_of(lines: list[str], owner: _Owner) -> Docstring | None:
    first = owner.body[0] if owner.body else None
    if not isinstance(first, ast.Expr) or not isinstance(first.value, ast.Constant):
        return None
    node = first.value
    if not isinstance(node.value, str):
        return None
    text = _docstring_text(lines, node)
    return Docstring(node.lineno, node.lineno + len(text) - 1, text)


def _decorator_name(node: ast.expr) -> str:
    """The dotted name a decorator is written with, or an empty string for any other form."""
    used = node.func if isinstance(node, ast.Call) else node
    parts: list[str] = []
    while isinstance(used, ast.Attribute):
        parts.append(used.attr)
        used = used.value
    if not isinstance(used, ast.Name):
        return ""
    parts.append(used.id)
    return ".".join(reversed(parts))


def python_docstrings(source: str) -> list[Docstring]:
    """Find the module, class and function docstrings in Python source, in line order."""
    tree = _parse(source)
    lines = _LINE_BREAK.split(source)
    found: list[Docstring] = []
    for owner in ast.walk(tree):
        if isinstance(owner, _OWNERS):
            docstring = _docstring_of(lines, owner)
            if docstring is not None:
                found.append(docstring)
    return sorted(found)


def module_docstring(source: str) -> list[Docstring]:
    """Find the docstring of the module itself, or nothing when it has none."""
    tree = _parse(source)
    found = _docstring_of(_LINE_BREAK.split(source), tree)
    return [] if found is None else [found]


def decorated_docstrings(source: str, decorator: str) -> list[Docstring]:
    """Find the docstring of every function written with ``decorator``, named as in the source."""
    tree = _parse(source)
    lines = _LINE_BREAK.split(source)
    found: list[Docstring] = []
    for owner in ast.walk(tree):
        if isinstance(owner, _FUNCTIONS) and any(
            _decorator_name(used) == decorator for used in owner.decorator_list
        ):
            docstring = _docstring_of(lines, owner)
            if docstring is not None:
                found.append(docstring)
    return sorted(found)
