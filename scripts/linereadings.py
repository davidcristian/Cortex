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


def split(search_text: str, line: str) -> tuple[str, str, int]:
    """The opening and closing runs in ``line`` that cover the most of ``search_text``."""
    best = ("", "", 0)
    for length in range(len(search_text) + 1):
        start = line.find(search_text[:length])
        if start < 0:
            break
        stop = start + length
        closing = _closing(search_text[length:], line[stop:])
        if length + len(closing) >= len(best[0]) + len(best[1]):
            column = stop if length else line.find(closing) + len(closing)
            best = (search_text[:length], closing, column)
    return best


def _windows(text: str, span: int) -> list[tuple[int, str]]:
    """Each run of ``span`` consecutive lines of ``text``, with the offset it starts at."""
    lines = text.split("\n")
    starts = [0]
    for line in lines:
        starts.append(starts[-1] + len(line) + 1)
    return [(starts[at], "\n".join(lines[at : at + span])) for at in range(len(lines) - span + 1)]


def _placed(text: str, opening: str, closing: str, stop: int) -> LineRun:
    """A run ending at ``stop``, named on the line where its runs stop matching."""
    gap = stop if opening else stop - len(closing)
    opened = text.rfind("\n", 0, gap) + 1
    ends = text.find("\n", gap)
    words = text[opened : len(text) if ends < 0 else ends]
    return LineRun(line_of(text, gap), opening, closing, stop - opened, stop, words)


def _blanked(match: re.Match[str]) -> str:
    """A found occurrence with every character but its line breaks blanked out."""
    return "".join(character if character == "\n" else BLANK for character in match.group())


def line_runs(search_text: str, text: str, found: re.Pattern[str]) -> list[LineRun]:
    """Every place tied for the most of ``search_text``, read over as many lines as it spans."""
    read = found.sub(_blanked, text)
    best: list[LineRun] = []
    for offset, words in _windows(read, search_text.count("\n") + 1):
        opening, closing, column = split(search_text, words)
        run = _placed(text, opening, closing, offset + column)
        if not best or run.length > best[0].length:
            best = [run]
        elif run.length == best[0].length and all(each.stop != run.stop for each in best):
            best.append(run)
    if not best or 2 * best[0].length < len(search_text):
        return []
    return best


def _pieces(run: LineRun) -> str:
    """The runs on one line, as the fault quotes them."""
    if run.opening and run.closing:
        return f"its opening {run.opening!r} and its closing {run.closing!r}"
    if run.opening:
        return f"its opening {run.opening!r}"
    return f"its closing {run.closing!r}"


def said(runs: list[LineRun], search_text: str, at: int | None) -> str:
    """The clause naming the line with most of ``search_text``, or saying no line has half."""
    if not runs:
        return "with less than half of it on any line"
    run = next((each for each in runs if each.stop == at), runs[0])
    share = f"{run.length} of its {len(search_text)} characters ({_pieces(run)})"
    edge = len(run.opening or run.closing)
    read = quote(run.words, run.column - edge, run.column)
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


def short(search_text: str, text: str, found: re.Pattern[str]) -> str:
    """What a count that came up short says about the rest of the file, if anything."""
    runs = line_runs(search_text, text, found)
    return f"; outside those, the file is {said(runs, search_text, None)}"
