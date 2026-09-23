"""Find the string literals in source that hold prose, and the Python ones exempted by name."""

import ast
import re
from collections.abc import Callable, Container, Sequence
from pathlib import Path
from typing import NamedTuple

import bannedwords
import slashcomments
from commentblocks import SourceError
from slashcomments import PLACEHOLDER

_WORD = r"(?:\w+|\{\})"
_TWO_WORDS = re.compile(rf"{_WORD} +{_WORD}")
_PATH_OR_FLAG = re.compile(r"(?<!\S)(?:-{1,2}[A-Za-z]\S*|\S*/\S*|\S+\.[A-Za-z]\w*)")
_MASK = "\0"
_ESCAPE = re.compile(r"\\(.)")
_BLANK_ESCAPES = frozenset("nrt")
_OWNERS = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
SLASH_SUFFIXES = frozenset({".rs", ".ts", ".tsx"})
MODEL_INPUT = "A model reads this text, so changing a word needs a model measurement first."


class ExemptionError(Exception):
    """An exemption names a file, a docstring or a string that is no longer there."""


class Literal(NamedTuple):
    """One string literal read as prose, and the module-level name it is assigned to, if any."""

    line: int
    text: str
    name: str | None


class LiteralExemption(NamedTuple):
    """Module-level names in one file whose string literals the prose check leaves alone."""

    path: str
    names: tuple[str, ...]
    reason: str


EXEMPTIONS = (
    LiteralExemption(
        path="brain/packages/core/src/cortex_core/untrusted.py",
        names=("SECURITY_PREAMBLE",),
        reason=MODEL_INPUT,
    ),
    LiteralExemption(
        path="brain/packages/core/src/cortex_core/recap_prompt.py",
        names=("_PREFACE",),
        reason=MODEL_INPUT,
    ),
    LiteralExemption(
        path="brain/packages/core/src/cortex_core/spawn_spec.py",
        names=("_CHOICE_NOTE",),
        reason=MODEL_INPUT,
    ),
    LiteralExemption(
        path="brain/packages/orchestrator/src/cortex_orchestrator/config_subagents.py",
        names=("DEFAULT_SUBAGENT_DESCRIPTION",),
        reason=MODEL_INPUT,
    ),
    LiteralExemption(
        path="brain/packages/email/src/cortex_email/values.py",
        names=("_FILENAME_HELP", "SEARCH_REFUSED", "FOLDER_HELP", "FOLDER_UNKNOWN"),
        reason=MODEL_INPUT,
    ),
    LiteralExemption(
        path="brain/packages/orchestrator/src/cortex_orchestrator/own_texts.py",
        names=("SEARCH_REFUSED", "FOLDER_UNKNOWN"),
        reason="Each is the email sidecar's own text word for word, which crosscheck.py compares.",
    ),
)


def reads_literals(relative: Path) -> bool:
    """Return whether the check reads the string literals of the file at ``relative``."""
    match relative.parts:
        case ("scripts", _) | ("brain", "packages", _, "src", _, *_):
            return relative.suffix == ".py"
        case ("body", *inside) if "tests" not in inside:
            return relative.suffix in SLASH_SUFFIXES and not relative.stem.endswith(".test")
        case _:
            return False


def _unread(tree: ast.Module) -> set[int]:
    unread: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, _OWNERS):
            unread.update(id(first.value) for first in node.body[:1] if isinstance(first, ast.Expr))
        elif isinstance(node, ast.Dict):
            unread.update(id(key) for key in node.keys)
        elif isinstance(node, ast.Subscript):
            unread.add(id(node.slice))
        elif isinstance(node, ast.JoinedStr):
            unread.update(id(value) for value in node.values)
    return unread


def _text(node: ast.Constant | ast.JoinedStr) -> str | None:
    if isinstance(node, ast.JoinedStr):
        return "".join(
            str(value.value) if isinstance(value, ast.Constant) else PLACEHOLDER
            for value in node.values
        )
    return node.value if isinstance(node.value, str) else None


def _assigned(statement: ast.stmt) -> str | None:
    if isinstance(statement, ast.Assign) and isinstance(statement.targets[0], ast.Name):
        return statement.targets[0].id
    return None


def _masked(text: str) -> str:
    flat = bannedwords.mask(text.replace("\n", " "))
    return _PATH_OR_FLAG.sub(lambda found: _MASK * len(found.group()), flat)


def _unescaped(text: str) -> str:
    return _ESCAPE.sub(lambda found: " " if found[1] in _BLANK_ESCAPES else found[1], text)


def slash_literals(source: str, syntax: slashcomments.Syntax) -> list[Literal]:
    """Return the Rust or TypeScript literals in ``source`` that hold two words, masked."""
    found: list[Literal] = []
    for line, text in slashcomments.slash_strings(source, syntax):
        if _TWO_WORDS.search(masked := _masked(_unescaped(text))):
            found.append(Literal(line=line, text=masked, name=None))
    return found


def file_literals(relative: Path, source: str) -> list[Literal]:
    """Return the prose literals of the file at ``relative``, read by the lexer its suffix names."""
    if relative.suffix in SLASH_SUFFIXES:
        return slash_literals(source, slashcomments.SYNTAXES[relative.suffix])
    return prose_literals(source)


def prose_literals(source: str) -> list[Literal]:
    """Return the literals in ``source`` that hold two words separated by a space, masked.

    Docstrings, dict keys and subscripts are not read; paths, flags and code spans are masked.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError as err:
        raise SourceError(str(err)) from err
    unread = _unread(tree)
    found: list[Literal] = []
    for statement in tree.body:
        name = _assigned(statement)
        for node in ast.walk(statement):
            if not isinstance(node, ast.Constant | ast.JoinedStr) or id(node) in unread:
                continue
            text = _text(node)
            if text is not None and _TWO_WORDS.search(masked := _masked(text)):
                found.append(Literal(line=node.lineno, text=masked, name=name))
    return sorted(found)


def literal_runs(
    literals: Sequence[Literal], exempt: Container[str | None]
) -> list[list[bannedwords.Line]]:
    """Return one run per literal whose name is not in ``exempt``."""
    return [[(item.line, item.text)] for item in literals if item.name not in exempt]


def exempt_names(
    root: Path,
    exemptions: Sequence[LiteralExemption],
    pattern: re.Pattern[str],
    read: Callable[[Path], str],
) -> dict[Path, frozenset[str]]:
    """Return the names each exemption covers, and fail when one names a string with no hit."""
    covered: dict[Path, frozenset[str]] = {}
    for item in exemptions:
        path = Path(item.path)
        if not (root / path).is_file():
            msg = f"the exemption for {item.path} names a file that is not there"
            raise ExemptionError(msg)
        literals = prose_literals(read(root / path))
        for name in item.names:
            runs = literal_runs([found for found in literals if found.name == name], ())
            if not any(bannedwords.find_words(run, pattern) for run in runs):
                msg = (
                    f"the exemption for {item.path} names {name}, "
                    "and no string assigned to it holds a banned word"
                )
                raise ExemptionError(msg)
        covered[path] = covered.get(path, frozenset()) | frozenset(item.names)
    return covered
