"""What the recall trail's widest field really costs a line, read off lines a container wrote.

`cortex_core.VALUE_CHARS` bounds one rendered field at 2,048 characters, and the argument that the
bound is generous enough rests on one comparison: it has to clear the widest value the tree
attaches, which is the recall trail's `dropped` list at the shipped pool of twenty. That figure was
drawn in process, from `uuid4` ids and cosine scores a script made up, with no store involved. The
ids a live stack mints and the cosines pgvector returns are both inputs to the rendered width, so
the figure was a number about a synthesis rather than about the trail.

This is the reading half of the live run that answers it (ADR-0038 real-trail addendum), and it is
in this tree for the reasons `contrast.py` is: it must be pure, it must never ship inside the brain
image, and it must be covered like everything else. The measuring half is
`brain/packages/orchestrator/tests/recall_trail_probe.py`, which runs inside the brain container
and writes real trail lines; `just recall-width` runs both. What arrives here is captured text, and
what leaves is the distribution of that field's rendered width and of the whole line's.

**The line, because the capture has it whole and one open question is about nothing else.** The
per-value bound leaves the line itself unbounded, and what says that cannot bite today is an
arithmetic argument about how many bounded fields fit under the cliff a container's log driver ends
a message at. Nothing had measured a real line against it, though every line this reads is one, so
the width is reported beside the field's in the same cohorts. The recall trail is the widest line
the brain writes, which is what makes this the reading rather than a reading: if anything the
deployment logs approaches that cliff, it is one of these.

**What the line's width is measured from is the rendering and not the captured text.** A capture
taken through `docker compose logs` opens every line with a service prefix the process never wrote,
so a length counted off the file would be a reading of the capture's own decoration. The width here
starts where the shipped formatter's output starts, which is `logging.BASIC_FORMAT`'s level, logger
and message. Finding that opening is also what qualifies a line: matching the message where the
formatter puts it, rather than anywhere in the text, is what tells the message from the logger's
own name, which ends in the same word.

**A line the driver split is invisible here, and the reading is still right.** Past the cliff a
message continues in a second piece carrying no newline, so the plainest capture reads it back
concatenated: the width measured is the width the process wrote, which is the number this reports.
What is lost is the fact of the split, and the `-t` capture that would show it stamps every piece
mid line, inflating the very width being measured (ADR-0038 bounded-value addendum). The two
readings cannot be taken at once, and this is the one that answers the question.

**Why a range and an interval rather than a maximum.** The claim under test is about a maximum, and
a maximum from one run is the weakest thing a run can publish: it can only grow with n. So a block
reports its whole shape, and a second block run separately is the check, two samples of a maximum
agreeing being the standard the synthesised figure already met. The bootstrap interval on the mean
is the part that does have a sampling distribution, and it is seeded and printed with its seed, so
the arithmetic is reproducible without the stack. That interval is the field's alone: the line is
read for its ceiling against a cliff, and an interval on a mean says nothing about a ceiling, where
the field's mean is the quantity a synthesised figure was once compared against.

**Width is reported against the number of candidates the line carried**, and that is the reading
rather than a garnish. This field is a sum over its entries, so a line whose rank kept four notes
and a line whose rank kept none are two different quantities and pooling them describes neither.
The widest case is the whole pool, which is what a rank that keeps nothing drops, and it is the one
cohort a claim about the widest value the tree attaches is actually about.

**The one thing this reads that is not arithmetic** is whether a rendering was cut. A cut value
ends in `render_value`'s own marker, and its presence on a trail line would say the bound bit a
line that ships, which is exactly the failure the bound was sized to avoid. It is reported as a
count rather than folded into the cohorts, because a cut rendering measures the bound rather than
the field, and it no longer parses, so it has no candidate count to be grouped under either.
"""

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
# The field whose width is the subject. Spelled once and spent in the pattern below.
TRAIL_FIELD = "dropped"
# One field's rendering, bounded by the next `name=` pair or by the end of the line. The trail's
# own JSON is compact and carries no space at all, so this could have stopped at the next space,
# and deliberately does not: a rendering the bound CUT ends in a marker that carries two spaces,
# and stopping at the first of them would report a cut field as a whole one 2,048 characters wide.
_VALUE = re.compile(rf" {TRAIL_FIELD}=(?P<value>.*?)(?= [A-Za-z_][A-Za-z0-9_]*=|$)")
# What `cortex_core.CUT` renders as, anchored at the end, since that is the only place it can sit
# on a value the bound cut.
_CUT = re.compile(r"<cut \d+ chars>$")
# Where the shipped rendering of one record starts: `logging.BASIC_FORMAT`'s level, logger and
# message, which is what `PlainFormatter` builds on and therefore what the process wrote. Anything
# in front of it belongs to whoever read the log back. The level is any run of capitals rather than
# the five names `logging` ships, which is the claim this actually rests on, and the logger is
# whatever sits between the two colons, its own name carrying no colon and no space.
_RECORD = re.compile(rf"[A-Z]+:[^\s:]+:{re.escape(TRAIL_MESSAGE)}(?= |$)")


class TrailWidthError(Exception):
    """A capture is unreadable, or holds no trail line to measure."""


class Reading(NamedTuple):
    """One trail line: the field's width, the whole line's, the candidates named, and if cut.

    ``width`` is the field's rendering and ``line`` is the record's, the field's own characters
    included, measured from where the formatter's output starts rather than from the start of the
    captured text.

    ``entries`` is ``None`` for a rendering the bound cut, which is not a shortfall in the parser:
    a cut rendering has lost its closing bracket by construction, so the number of candidates it
    was about is genuinely no longer on the line.
    """

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
    """One line's reading, or ``None`` when the line is not a trail line carrying the field.

    A line qualifies by opening a record with the trail's own message and by carrying that field;
    a line carrying the message and no such field is a trail line this build attaches no such
    field on, and has no width to report.
    """
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
    """Read one capture into a block, refusing a file that holds no trail line at all."""
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
    """Every whole rendering across the blocks, grouped by how many candidates it named.

    The readings and not their widths, because a cohort is now read twice: the field a claim about
    the widest value is about, and the line that field sits on, which is one number in the same
    grouping rather than a second grouping beside it.
    """
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
