"""Read the banned-word table in AGENTS.md and find those words in prose."""

import re
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import NamedTuple

RULES = Path(__file__).resolve().parent.parent / "AGENTS.md"
HEADER = "Do not write"

_SEPARATOR = re.compile(r":?-+:?")
_CODE_SPAN = re.compile(r"(?<!`)(`+)(?!`).+?(?<!`)\1(?!`)", re.DOTALL)
_LINK_TARGET = re.compile(r"(?<=\])\([^)]*\)")
_LINK_DEFINITION = re.compile(r"^[ \t]*\[[^\]\n]+\]:[ \t]*\S+", re.MULTILINE)
_URL = re.compile(r"\b[a-z][a-z0-9+.-]*://\S+", re.IGNORECASE)
_MASKS = (_CODE_SPAN, _LINK_TARGET, _LINK_DEFINITION, _URL)
_MASK = "\0"

Line = tuple[int, str]


class TableError(Exception):
    """The banned-word table is missing, empty or cannot be read."""


class Table(NamedTuple):
    """The banned words, and the first and last line of the table that lists them."""

    words: tuple[str, ...]
    first: int
    last: int


class Hit(NamedTuple):
    """One banned word found on one line."""

    line: int
    word: str


def _cells(line: str) -> list[str]:
    text = line.strip()
    if not text.startswith("|"):
        return []
    return [cell.strip() for cell in text.strip("|").split("|")]


def parse_table(text: str, name: str) -> Table:
    """Return the table whose first column is headed ``HEADER``; ``name`` is used in errors."""
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if _cells(line)[:1] != [HEADER]:
            continue
        rows: list[list[str]] = []
        for row in lines[index + 1 :]:
            cells = _cells(row)
            if not cells:
                break
            rows.append(cells)
        words = tuple(
            word.strip().lower()
            for cells in rows
            if not all(_SEPARATOR.fullmatch(cell) for cell in cells)
            for word in cells[0].split(",")
            if word.strip()
        )
        if not words:
            msg = f"the banned-word table in {name} lists no word"
            raise TableError(msg)
        return Table(words=words, first=index + 1, last=index + 1 + len(rows))
    msg = f"{name} has no table whose first column is headed {HEADER!r}"
    raise TableError(msg)


def read_table(path: Path) -> Table:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as err:
        msg = f"cannot read {path}: {err}"
        raise TableError(msg) from err
    return parse_table(text, str(path))


def compile_words(words: Iterable[str]) -> re.Pattern[str]:
    """Return one pattern matching any of ``words`` as a whole word, in any case.

    The words of a phrase may be separated by any whitespace, including one line break.
    """
    phrases = {r"\s+".join(map(re.escape, word.split())) for word in words}
    longest_first = sorted(phrases, key=lambda phrase: (-len(phrase), phrase))
    return re.compile(rf"(?<!\w)(?:{'|'.join(longest_first)})(?!\w)", re.IGNORECASE)


def mask(text: str) -> str:
    """Blank out code spans, link targets and URLs, keeping line breaks where they were."""
    for pattern in _MASKS:
        text = pattern.sub(lambda found: re.sub(r"[^\n]", _MASK, found.group()), text)
    return text


def runs(lines: Iterable[Line]) -> list[list[Line]]:
    """Split numbered lines into runs of consecutive, non-blank lines."""
    grouped: list[list[Line]] = []
    for number, text in lines:
        if not text.strip():
            continue
        if grouped and grouped[-1][-1][0] == number - 1:
            grouped[-1].append((number, text))
        else:
            grouped.append([(number, text)])
    return grouped


def find_words(run: Sequence[Line], pattern: re.Pattern[str]) -> list[Hit]:
    """Return every banned word in one run of consecutive lines, on the line where it starts."""
    masked = mask("\n".join(text for _, text in run)).split("\n")
    hits: list[Hit] = []
    for index, (number, _) in enumerate(run):
        here = masked[index]
        following = masked[index + 1] if index + 1 < len(masked) else ""
        hits.extend(
            Hit(line=number, word=" ".join(found.group().split()).lower())
            for found in pattern.finditer(f"{here}\n{following}")
            if found.start() < len(here)
        )
    return hits
