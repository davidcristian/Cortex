"""What a fault says about one line: its number, its text, and its share of the search text."""

import re
from typing import NamedTuple

# Wide enough for the sentence around a value, which is what tells a homonym from the real
# thing, and bounded because a runbook table row runs past a thousand characters.
QUOTED_WIDTH = 100

TRIMMED = "..."

BLANK = "\0"


def line_of(text: str, at: int) -> int:
    """The one-based line the offset ``at`` falls on."""
    return text.count("\n", 0, at) + 1


def quote(line: str, start: int, end: int) -> str:
    """``line`` around the span ``start``..``end``, trimmed to a width a fault can print."""
    if len(line.strip()) <= QUOTED_WIDTH:
        return line.strip()
    margin = max(QUOTED_WIDTH - (end - start), 0) // 2
    opened = max(start - margin, 0)
    closed = min(end + margin, len(line))
    lead = "" if opened == 0 else TRIMMED
    trail = "" if closed == len(line) else TRIMMED
    return f"{lead}{line[opened:closed].strip()}{trail}"


class LineRun(NamedTuple):
    """How much of the search text one line has, and where on the line the match stops."""

    number: int
    opening: str
    closing: str
    column: int
    stop: int
    words: str

    @property
    def length(self) -> int:
        """How many characters of the search text the line has."""
        return len(self.opening) + len(self.closing)


def _closing(tail: str, rest: str) -> str:
    """The longest closing run of ``tail`` that ``rest`` contains, which may be none of it."""
    length = 0
    while length < len(tail) and tail[len(tail) - length - 1 :] in rest:
        length += 1
    return tail[len(tail) - length :]


def split(needle: str, line: str) -> tuple[str, str, int]:
    """The opening and closing runs in ``line`` that cover the most of ``needle``."""
    best = ("", "", 0)
    for length in range(len(needle) + 1):
        start = line.find(needle[:length])
        if start < 0:
            break
        stop = start + length
        closing = _closing(needle[length:], line[stop:])
        if length + len(closing) >= len(best[0]) + len(best[1]):
            column = stop if length else line.find(closing) + len(closing)
            best = (needle[:length], closing, column)
    return best


def line_runs(needle: str, text: str, found: re.Pattern[str]) -> list[LineRun] | None:
    """Every line tied for having the most of ``needle`` on it, once ``found`` is blanked out."""
    if "\n" in needle:
        return None
    best: list[LineRun] = []
    offset = 0
    for number, words in enumerate(text.split("\n"), start=1):
        read = found.sub(lambda match: BLANK * len(match.group()), words)
        opening, closing, column = split(needle, read)
        run = LineRun(number, opening, closing, column, offset + column, words)
        offset += len(words) + 1
        if not best or run.length > best[0].length:
            best = [run]
        elif run.length == best[0].length:
            best.append(run)
    if 2 * best[0].length < len(needle):
        return []
    return best


def _pieces(run: LineRun) -> str:
    """The runs on one line, as the fault quotes them."""
    if run.opening and run.closing:
        return f"its opening {run.opening!r} and its closing {run.closing!r}"
    if run.opening:
        return f"its opening {run.opening!r}"
    return f"its closing {run.closing!r}"


def said(runs: list[LineRun], needle: str, at: int | None) -> str:
    """The clause naming the line with the most of ``needle``, or saying no line has half of it."""
    if not runs:
        return "with less than half of it on any line"
    run = next((each for each in runs if each.stop == at), runs[0])
    share = f"{run.length} of its {len(needle)} characters ({_pieces(run)})"
    carried = len(run.opening or run.closing)
    read = quote(run.words, run.column - carried, run.column)
    if len(runs) == 1:
        return f"with the most of it on line {run.number}, {share}, where it reads {read!r}"
    which = "the first" if at is None else "the nearest to that form"
    return (
        f"with the most of it on {len(runs)} lines, {share} each, {which} on line "
        f"{run.number}, where it reads {read!r}"
    )


def counted(text: str, matches: list[re.Match[str]]) -> str:
    """The lines a counted mention's occurrences were found on, as the count's own clause."""
    numbers = [str(line_of(text, match.start())) for match in matches]
    if len(numbers) == 1:
        return f" (on line {numbers[0]})"
    return f" (on lines {', '.join(numbers[:-1])} and {numbers[-1]})"


def short(needle: str, text: str, found: re.Pattern[str]) -> str:
    """What a count that came up short says about the rest of the file, if anything."""
    runs = line_runs(needle, text, found)
    if runs is None:
        return ""
    return f"; outside those, the file is {said(runs, needle, None)}"
