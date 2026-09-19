"""Report banned words in prose, and docstrings or comment blocks longer than three lines."""

import argparse
import re
import sys
from collections import Counter
from collections.abc import Callable, Container, Iterator, Sequence
from functools import partial
from pathlib import Path
from typing import NamedTuple

import bannedwords
import commentblocks
import slashcomments
from commentblocks import Block, Comments, Docstring, SourceError
from dashcheck import IgnoreQueryError, ignored_paths
from markdownfences import Fences
from treewalk import walk_files

MAX_LINES = 3
RULES_NAME = "AGENTS.md"
MARKDOWN = ".md"
PYTHON = frozenset({".py", ".pyi"})
HASH_SUFFIXES = frozenset({".yml", ".yaml", ".toml", ".sh", ".conf"})
HASH_NAMES = frozenset({"justfile", ".gitignore", ".dockerignore"})
DOCKERFILE = "Dockerfile"
SQL = ".sql"
EXTRA_SKIPS = frozenset({"_generated"})
MIN_FILES = 1

BANNED = "banned word"
DOCSTRING = "docstring"
BLOCK = "comment block"


class UnreadableFileError(Exception):
    """A file cannot be read or parsed, or a path is not inside the root."""


class ExemptionError(Exception):
    """An exemption names a file or a docstring that is no longer there."""


class Exemption(NamedTuple):
    """Docstrings this check leaves alone: the module docstring when ``decorator`` is None, and
    otherwise the docstrings of the functions written with that decorator.
    """

    path: str
    decorator: str | None
    reason: str


EXEMPTIONS = (
    Exemption(
        path="scripts/registry.py",
        decorator=None,
        reason="This module docstring is the list of registry parts test_crosscheck.py reads.",
    ),
    Exemption(
        path="brain/packages/email/src/cortex_email/server.py",
        decorator="server.tool",
        reason="These docstrings are the tool descriptions a model reads, not documentation.",
    ),
)


class Prose(NamedTuple):
    """What one file holds: runs of prose lines, comment blocks and docstrings."""

    runs: list[list[bannedwords.Line]]
    blocks: list[Block]
    docstrings: list[Docstring]


class Problem(NamedTuple):
    """One rule broken on one line."""

    path: Path
    line: int
    kind: str
    message: str


class Scan(NamedTuple):
    """The number of files read and every problem found in them."""

    files: int
    problems: list[Problem]


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


def check_prose(
    path: Path, prose: Prose, pattern: re.Pattern[str], exempt: Container[int] = ()
) -> list[Problem]:
    """Return the problems in one file's prose; lines in ``exempt`` are not checked at all."""
    problems = [
        Problem(path, hit.line, BANNED, f'banned word "{hit.word}"')
        for run in prose.runs
        for hit in bannedwords.find_words([line for line in run if line[0] not in exempt], pattern)
    ]
    for kind, found in [(DOCSTRING, prose.docstrings), (BLOCK, prose.blocks)]:
        problems.extend(
            Problem(path, item.first, kind, f"{kind} has {item.lines} lines, at most {MAX_LINES}")
            for item in found
            if item.lines > MAX_LINES and item.first not in exempt
        )
    return sorted(problems)


def exempt_lines(root: Path, exemptions: Sequence[Exemption]) -> dict[Path, frozenset[int]]:
    """Return the lines each exemption covers, and fail when one names what is not there."""
    covered: dict[Path, frozenset[int]] = {}
    for item in exemptions:
        path = Path(item.path)
        if not (root / path).is_file():
            msg = f"the exemption for {item.path} names a file that is not there"
            raise ExemptionError(msg)
        text = _read(root / path)
        if item.decorator is None:
            found = commentblocks.module_docstring(text)
            target = "the module docstring"
        else:
            found = commentblocks.decorated_docstrings(text, item.decorator)
            target = f"docstrings under @{item.decorator}"
        if not found:
            msg = f"the exemption for {item.path} names {target}, which is not there"
            raise ExemptionError(msg)
        covered[path] = covered.get(path, frozenset()) | frozenset(
            line for docstring in found for line in range(docstring.first, docstring.last + 1)
        )
    return covered


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as err:
        msg = f"cannot read {path}: {err}"
        raise UnreadableFileError(msg) from err


def _walk(root: Path, directory: Path, ignored: frozenset[str]) -> Iterator[Path]:
    def enter(inside: Path) -> bool:
        return (directory / inside).as_posix() not in ignored

    for path in walk_files(root / directory, also_skip=EXTRA_SKIPS, enter=enter):
        found = directory / path.relative_to(root / directory)
        if found.as_posix() not in ignored:
            yield found


def _candidates(root: Path, paths: list[Path]) -> Iterator[Path]:
    ignored = ignored_paths(root)
    for given in paths:
        try:
            relative = given.resolve().relative_to(root.resolve())
        except ValueError as err:
            msg = f"{given} is not inside {root}"
            raise UnreadableFileError(msg) from err
        if (root / relative).is_dir():
            yield from _walk(root, relative, ignored)
        else:
            yield relative


def scan(root: Path, paths: list[Path], pattern: re.Pattern[str], table: range) -> Scan:
    """Check the files at and under ``paths``; ``table`` is the line range of the word table."""
    files = 0
    problems: list[Problem] = []
    exempt = exempt_lines(root, EXEMPTIONS)
    for relative in _candidates(root, paths):
        reader = reader_for(relative.name)
        if reader is None:
            continue
        text = _read(root / relative)
        try:
            prose = reader(text)
        except SourceError as err:
            msg = f"cannot parse {relative}: {err}"
            raise UnreadableFileError(msg) from err
        files += 1
        skip = table if relative == Path(RULES_NAME) else exempt.get(relative, frozenset())
        problems.extend(check_prose(relative, prose, pattern, skip))
    return Scan(files=files, problems=problems)


def main(argv: list[str] | None = None) -> int:
    """Run the check, print every problem, and return the exit code."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(),
        help="the repository: its AGENTS.md lists the banned words (default: current directory)",
    )
    parser.add_argument(
        "paths", nargs="*", type=Path, help="files or directories to check (default: the root)"
    )
    args = parser.parse_args(argv)
    root: Path = args.root
    paths: list[Path] = args.paths or [root]
    if not root.is_dir():
        print(f"prosecheck: root {root} is not a directory", file=sys.stderr)
        return 2
    try:
        table = bannedwords.read_table(root / RULES_NAME)
        pattern = bannedwords.compile_words(table.words)
        scanned = scan(root, paths, pattern, range(table.first, table.last + 1))
    except (
        bannedwords.TableError,
        IgnoreQueryError,
        UnreadableFileError,
        ExemptionError,
        SourceError,
    ) as err:
        print(f"prosecheck: {err}", file=sys.stderr)
        return 2
    if scanned.files < MIN_FILES:
        print(
            "prosecheck: no file of a checked type was read, so nothing was checked",
            file=sys.stderr,
        )
        return 2
    for problem in scanned.problems:
        print(f"{problem.path}:{problem.line}: {problem.message}")
    if scanned.problems:
        kinds = Counter(problem.kind for problem in scanned.problems)
        print(
            f"\nprosecheck: {kinds[BANNED]} banned word(s), {kinds[DOCSTRING]} long docstring(s) "
            f"and {kinds[BLOCK]} long comment block(s) in {scanned.files} file(s) read",
            file=sys.stderr,
        )
        return 1
    print(
        f"prosecheck OK: {scanned.files} file(s) read, with no banned word and no docstring "
        f"or comment block over {MAX_LINES} lines"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover -- command line entry; main() is tested
    sys.exit(main())
