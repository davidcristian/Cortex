"""What the recall trail's widest field really costs a line, read off lines a container wrote."""

import argparse
import json
import re
import statistics
import sys
from pathlib import Path
from typing import NamedTuple, cast

from contrast import DEFAULT_RESAMPLES, DEFAULT_SEED, bootstrap

# The message `LoggingRecallSink` writes, which is what tells a trail line from every other line in
# a capture. Matched where the formatter puts a message rather than anywhere in the line, by the
# pattern below, since the logger this sink writes through ends in the same word.
TRAIL_MESSAGE = "memory.recall"
# The field whose width is the subject. Written once and spent in the pattern below.
TRAIL_FIELD = "dropped"
_VALUE = re.compile(rf" {TRAIL_FIELD}=(?P<value>.*?)(?= [A-Za-z_][A-Za-z0-9_]*=|$)")
# What `cortex_core.CUT` renders as, anchored at the end, since that is the only place it can sit
# on a value the bound cut.
_CUT = re.compile(r"<cut \d+ chars>$")
_RECORD = re.compile(rf"[A-Z]+:[^\s:]+:{re.escape(TRAIL_MESSAGE)}(?= |$)")


class TrailWidthError(Exception):
    """A capture is unreadable, or holds no trail line to measure."""


class Reading(NamedTuple):
    """One trail line: the field's width, the whole line's, the candidates named, and if cut."""

    width: int
    line: int
    entries: int | None
    cut: bool


class Block(NamedTuple):
    """One capture's readings: where it came from, and one reading per trail line in it."""

    path: Path
    readings: tuple[Reading, ...]

    @property
    def widths(self) -> tuple[int, ...]:
        """Every reading's field width, in the order the capture carried them."""
        return tuple(reading.width for reading in self.readings)

    @property
    def lines(self) -> tuple[int, ...]:
        """Every reading's whole-line width, in the same order."""
        return tuple(reading.line for reading in self.readings)

    @property
    def cut(self) -> int:
        """How many of this block's renderings the bound cut."""
        return sum(1 for reading in self.readings if reading.cut)


class Shape(NamedTuple):
    """The distribution of one cohort's widths, in the terms a maximum claim is argued in."""

    n: int
    low: int
    median: float
    high: int


def read_line(line: str) -> Reading | None:
    """One line's reading, or ``None`` when the line is not a trail line carrying the field."""
    opened = _RECORD.search(line)
    if opened is None:
        return None
    match = _VALUE.search(line)
    if match is None:
        return None
    value = match.group("value")
    cut = _CUT.search(value) is not None
    return Reading(len(value), len(line) - opened.start(), None if cut else _entries(value), cut)


def _entries(value: str) -> int | None:
    """How many candidates a whole rendering names, or ``None`` when it will not parse as a list."""
    try:
        parsed: object = json.loads(value)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, list):
        return None
    return len(cast("list[object]", parsed))


def readings(text: str) -> tuple[Reading, ...]:
    """Every trail line's reading in ``text``, in the order the capture carried them."""
    found = (read_line(line) for line in text.splitlines())
    return tuple(reading for reading in found if reading is not None)


def load(path: Path) -> Block:
    """Read one capture into a block, raising on a file that holds no trail line at all."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as err:
        msg = f"{path}: unreadable capture ({err})"
        raise TrailWidthError(msg) from err
    found = readings(text)
    if not found:
        msg = f"{path}: no {TRAIL_MESSAGE} line carrying a {TRAIL_FIELD} field"
        raise TrailWidthError(msg)
    return Block(path, found)


def shape(widths: list[int]) -> Shape:
    """A cohort's count, floor, median and ceiling."""
    return Shape(len(widths), min(widths), statistics.median(widths), max(widths))


def by_entries(blocks: list[Block]) -> dict[int, list[Reading]]:
    """Every whole rendering across the blocks, grouped by how many candidates it named."""
    grouped: dict[int, list[Reading]] = {}
    for block in blocks:
        for reading in block.readings:
            if reading.entries is not None:
                grouped.setdefault(reading.entries, []).append(reading)
    return grouped


def report(blocks: list[Block], *, resamples: int, seed: int) -> str:
    """The whole reading: each block's shape, then the cohorts a maximum claim is argued over."""
    lines = [
        f"blocks: {len(blocks)}, resamples: {resamples}, seed: {seed}",
        "",
        f"per block, the rendered width of the trail's {TRAIL_FIELD} field:",
    ]
    for block in blocks:
        seen = shape(list(block.widths))
        mean = bootstrap([float(width) for width in block.widths], resamples=resamples, seed=seed)
        lines.append(
            f"  {block.path.name} (n={seen.n}): {seen.low} to {seen.high} chars,"
            f" median {seen.median:.1f}, mean {mean.point:.1f}"
            f" (95% CI {mean.low:.1f} to {mean.high:.1f}), cut {block.cut}"
        )
    lines.extend(["", "per block, the rendered width of the whole line that field sits on:"])
    for block in blocks:
        whole = shape(list(block.lines))
        lines.append(
            f"  {block.path.name} (n={whole.n}): {whole.low} to {whole.high} chars,"
            f" median {whole.median:.1f}"
        )
    grouped = by_entries(blocks)
    lines.extend(["", "over every block, by the candidates one line named:"])
    for entries in sorted(grouped):
        cohort = shape([reading.width for reading in grouped[entries]])
        whole = shape([reading.line for reading in grouped[entries]])
        # A rank that kept the whole pool drops nothing and renders the empty list, which is what
        # a deployment fetching exactly `k` produces on every recall. It has a width and no
        # per-candidate reading, so it is described rather than divided by.
        per = (
            f"{cohort.low / entries:.2f} to {cohort.high / entries:.2f} per candidate"
            if entries
            else "an empty list, so the whole width is the rendering's own syntax"
        )
        lines.append(
            f"  {entries:3d} dropped (n={cohort.n:4d}): {cohort.low} to {cohort.high} chars,"
            f" median {cohort.median:.1f}, {per},"
            f" whole line {whole.low} to {whole.high}"
        )
    every = [width for block in blocks for width in block.widths]
    wide = [width for block in blocks for width in block.lines]
    lines.extend(
        [
            "",
            f"over all {len(every)} trail lines: the field {min(every)} to {max(every)} chars,"
            f" the whole line {min(wide)} to {max(wide)}",
            f"cut by the bound: {sum(block.cut for block in blocks)}",
        ]
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """Read the captures, print the report, and return the process exit code."""
    parser = argparse.ArgumentParser(
        description=(
            "Report the rendered width of the recall trail's dropped field, and of the whole"
            " line it sits on, per captured block."
        ),
    )
    parser.add_argument("captures", type=Path, nargs="+", help="captured log text, one per block")
    parser.add_argument("--resamples", type=int, default=DEFAULT_RESAMPLES)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    args = parser.parse_args(argv)
    captures = cast("list[Path]", args.captures)
    resamples = cast("int", args.resamples)
    seed = cast("int", args.seed)
    try:
        if resamples <= 0:
            msg = "a bootstrap needs at least one resample"
            raise TrailWidthError(msg)  # noqa: TRY301 -- one refusal channel, caught just below
        print(report([load(path) for path in captures], resamples=resamples, seed=seed))
    except TrailWidthError as err:
        print(f"trailwidth: {err}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":  # pragma: no cover -- CLI entry point; main() is unit-tested
    sys.exit(main())
