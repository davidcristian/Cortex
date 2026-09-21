"""Find the prose a file holds: markdown outside code fences, comments and docstrings."""

from collections.abc import Callable
from functools import partial
from pathlib import Path
from typing import NamedTuple

import bannedwords
import commentblocks
import slashcomments
from commentblocks import Block, Comments, Docstring
from markdownfences import Fences

MARKDOWN = ".md"
PYTHON = frozenset({".py", ".pyi"})
HASH_SUFFIXES = frozenset({".yml", ".yaml", ".toml", ".sh", ".conf"})
HASH_NAMES = frozenset({"justfile", ".gitignore", ".dockerignore"})
DOCKERFILE = "Dockerfile"
SQL = ".sql"


class Prose(NamedTuple):
    """What one file holds: runs of prose lines, comment blocks and docstrings."""

    runs: list[list[bannedwords.Line]]
    blocks: list[Block]
    docstrings: list[Docstring]


def markdown_lines(text: str) -> list[bannedwords.Line]:
    """Return the numbered lines of a markdown document that are outside code fences."""
    fences = Fences()
    return [
        (number, line)
        for number, line in enumerate(text.split("\n"), start=1)
        if not fences.bounds(line) and not fences.inside
    ]


def _markdown(text: str) -> Prose:
    return Prose(runs=bannedwords.runs(markdown_lines(text)), blocks=[], docstrings=[])


def _from_comments(comments: Comments, docstrings: list[Docstring]) -> Prose:
    runs = bannedwords.runs((comment.line, comment.text) for comment in comments.lines)
    for docstring in docstrings:
        runs.extend(bannedwords.runs(enumerate(docstring.text, start=docstring.first)))
    return Prose(runs=runs, blocks=commentblocks.comment_blocks(comments), docstrings=docstrings)


def _python(text: str) -> Prose:
    return _from_comments(
        commentblocks.python_comments(text), commentblocks.python_docstrings(text)
    )


def _slash(syntax: slashcomments.Syntax, text: str) -> Prose:
    return _from_comments(slashcomments.slash_comments(text, syntax), [])


def _hash(marker: str, text: str) -> Prose:
    return _from_comments(commentblocks.hash_comments(text, marker), [])


def reader_for(name: str) -> Callable[[str], Prose] | None:
    """Return the function that finds the prose in a file called ``name``, or None if unchecked."""
    suffix = Path(name).suffix
    if suffix == MARKDOWN:
        return _markdown
    if suffix in PYTHON:
        return _python
    if suffix in slashcomments.SYNTAXES:
        return partial(_slash, slashcomments.SYNTAXES[suffix])
    if suffix in HASH_SUFFIXES or name in HASH_NAMES or name.startswith(DOCKERFILE):
        return partial(_hash, "#")
    if suffix == SQL:
        return partial(_hash, "--")
    return None
