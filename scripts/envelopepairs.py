"""How many cells two seeded runs of one envelope arm drew identically (ADR-0005).

`brain/packages/orchestrator/tests/test_envelope_cost_live.py` seeds every draw when
`CORTEX_ENVELOPE_SEED` is set, so two runs of one arm can be held against each other cell by cell.
This module counts, for every pair of the samples it is handed, the cells identical in `output` and
`tokens`, which is the count that addendum quotes. It is here rather than in the driver for the
reason `envelopefloor.py` is: a number a document quotes comes out of a file a gate covers.

A cell is matched on `question`, `draw` and `seed`. The samples are refused rather than counted
when a seed is null, since an unseeded run pairs with nothing; when one sample holds a cell twice;
when two samples do not hold the same cells; and when they are two arms, or a matched cell was
given another instruction or body, since identity between two prompts is not what a seed claims.
`envelopesamples.py` answers for the file format.

Reads the driver's own per-arm sample files, `just envelope-pairs measurements/envelope-*.json`.
Exit 0 published the counts, 1 refused to, 2 could not read a sample.
"""

import argparse
import sys
from itertools import combinations
from pathlib import Path
from typing import NamedTuple, cast

from envelopesamples import Cell, FloorError, cells

type Key = tuple[str, int | None, int | None]

# A pairing compares two samples at the least.
LEAST = 2


class Sample(NamedTuple):
    """One arm's sample as a paired reading holds it."""

    path: Path
    arm: str
    cells: tuple[Cell, ...]


def keyed(sample: Sample) -> dict[Key, Cell]:
    """The sample's cells by where each sits: its question, its draw and its seed."""
    return {(cell.question, cell.draw, cell.seed): cell for cell in sample.cells}


def where(key: Key) -> str:
    """One cell's place, as a report names it."""
    question, draw, seed = key
    return f"{question} draw {draw} seed {seed}"


def _alone(sample: Sample) -> str | None:
    """Why one sample cannot be paired with any other, or ``None`` when it can."""
    if any(cell.seed is None for cell in sample.cells):
        return f"{sample.path} carries a null seed, and an unseeded run pairs with nothing"
    if len(keyed(sample)) != len(sample.cells):
        return f"{sample.path} holds one cell twice"
    return None


def _against(first: Sample, other: Sample) -> str | None:
    """Why ``other`` does not line up with ``first``, or ``None`` when every cell does."""
    if other.arm != first.arm:
        return f"{other.path} is arm {other.arm} and {first.path} is arm {first.arm}"
    theirs, ours = keyed(other), keyed(first)
    if theirs.keys() != ours.keys():
        return f"{other.path} does not hold the cells {first.path} does"
    for key, cell in ours.items():
        if theirs[key].asked != cell.asked:
            return f"{other.path} was given another instruction or body at {where(key)}"
    return None


def refusal(samples: list[Sample]) -> str | None:
    """Why these samples cannot be compared cell by cell, or ``None`` when they can."""
    if len(samples) < LEAST:
        return "a pairing needs two samples or more"
    for sample in samples:
        alone = _alone(sample)
        if alone is not None:
            return alone
    for sample in samples[1:]:
        against = _against(samples[0], sample)
        if against is not None:
            return against
    return None


def differing(left: Sample, right: Sample) -> list[Key]:
    """The cells where ``right`` drew another completion than ``left``, in output or in tokens."""
    theirs = keyed(right)
    return [
        key
        for key, cell in keyed(left).items()
        if (cell.output, cell.tokens) != (theirs[key].output, theirs[key].tokens)
    ]


def publish(samples: list[Sample]) -> tuple[str, int]:
    """The report and the exit code: one line per pair of samples, or the reason there is none."""
    refused = refusal(samples)
    if refused is not None:
        return f"refused: {refused}", 1
    size = len(samples[0].cells)
    lines = [
        f"{len(samples)} samples of arm {samples[0].arm}, {size} cells each, matched on question,"
        " draw and seed:"
    ]
    for left, right in combinations(samples, 2):
        differ = differing(left, right)
        tail = f"; differ at {', '.join(where(key) for key in differ)}" if differ else ""
        lines.append(
            f"  {left.path} against {right.path}: {size - len(differ)} of {size} identical in"
            f" output and tokens{tail}"
        )
    return "\n".join(lines), 0


def main(argv: list[str] | None = None) -> int:
    """Read the samples, publish or refuse, and return the process exit code."""
    parser = argparse.ArgumentParser(
        description=(
            "Count the cells two or more seeded runs of one envelope arm drew identically, in"
            " output and in tokens, for every pair of them."
        ),
    )
    parser.add_argument("samples", type=Path, nargs="+", help="one envelope-<arm>.json per run")
    args = parser.parse_args(argv)
    try:
        samples = [Sample(path, *cells(path)) for path in cast("list[Path]", args.samples)]
    except FloorError as err:
        print(f"envelopepairs: {err}", file=sys.stderr)
        return 2
    report, code = publish(samples)
    print(report)
    return code


if __name__ == "__main__":  # pragma: no cover -- CLI entry point; main() is unit-tested
    sys.exit(main())
