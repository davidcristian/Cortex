"""The interval a live measurement reports: blocked paired arms, bootstrapped, seeded.

A live block of turns is measured by an integration-marked driver
(`brain/packages/orchestrator/tests/test_turn_cost_live.py`), one block per process, because an
arm is a container configuration and changing it means recreating the container. That puts the
arms in different processes, so no one of them can hold the whole comparison, and each writes a
JSON sample instead. This is what reads those samples back and says what they show.

The arithmetic lives here rather than in the driver. The measurement that moved the recall default
published a 0.515 s difference with a 95% interval and named no test, and the missing half was the
resampling that turned turns into an interval, which lived in a scratchpad and carried no seed.
Here it is a pure function of the samples, unit-tested at 100%, and reproducible from a seed
printed with every report.

The statistic, and why this one:

* **Blocked (paired) by question.** A turn's time is dominated by how long its answer is, which is
  a property of the question and not of the arm. Pooling turns across questions buries an arm's
  effect under between-question variance; pairing each question with itself removes it.
* **The mean of the per-question mean differences.** The mean is what a user pays over a session,
  and averaging within a question first keeps every question weighted equally however many
  repetitions it got.
* **A percentile bootstrap over the questions, not a t interval.** The resampling unit is the
  question, so n is the number of questions, which is far too small to lean on a normal
  approximation; and turn times are right-skewed, being bounded below by the model's own floor and
  unbounded above. A percentile bootstrap assumes neither.
* **Seeded.** The interval is then a function of the samples and the seed, both of which the report
  prints, so a reader can rerun the arithmetic without rerunning the GPU.

The first sample is the baseline and every later one is contrasted against it, which is what makes
an A/B/A run readable in one command: the second block is the arm under test and the third is the
same configuration as the first, so its contrast is a null whose interval ought to span zero. A
null that does not span zero says the run drifted and the arm contrast cannot be read; a null that
does span zero is what makes the arm contrast readable.
"""

import argparse
import json
import math
import random
import statistics
import sys
from pathlib import Path
from typing import NamedTuple, cast

# The 95% interval, as the two tails a percentile bootstrap reads off the resampled means.
LOW_TAIL = 0.025
HIGH_TAIL = 0.975
DEFAULT_RESAMPLES = 20000
DEFAULT_SEED = 20260808
# What a sample file carries per turn. Both are seconds; the first is the part a user feels.
METRICS = ("ttft", "wall")


class ContrastError(Exception):
    """A sample file is unreadable or malformed, or two blocks cannot be paired."""


class Block(NamedTuple):
    """One arm's sample: where it came from, what it called itself, and its turns."""

    path: Path
    arm: str
    turns: tuple[tuple[str, dict[str, float]], ...]


class Summary(NamedTuple):
    """The shape of one block's distribution for one metric."""

    n: int
    mean: float
    median: float
    sd: float


class Interval(NamedTuple):
    """A contrast: the point estimate and the bootstrap's two percentile bounds."""

    point: float
    low: float
    high: float


def _require(condition: bool, message: str) -> None:  # noqa: FBT001 -- a bare predicate is the point
    if not condition:
        raise ContrastError(message)


def load(path: Path) -> Block:
    """Read one sample file written by a live block driver."""
    try:
        raw = cast("object", json.loads(path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError) as err:
        msg = f"{path}: unreadable sample ({err})"
        raise ContrastError(msg) from err
    _require(isinstance(raw, dict), f"{path}: sample must be a JSON object")
    sample = cast("dict[str, object]", raw)
    arm = sample.get("arm")
    entries = sample.get("turns")
    _require(isinstance(arm, str), f"{path}: sample names no arm")
    _require(isinstance(entries, list), f"{path}: sample carries no turns list")
    turns: list[tuple[str, dict[str, float]]] = []
    for entry in cast("list[object]", entries):
        _require(isinstance(entry, dict), f"{path}: a turn is not a JSON object")
        turn = cast("dict[str, object]", entry)
        question = turn.get("question")
        _require(isinstance(question, str), f"{path}: a turn names no question")
        values = {name: turn.get(name) for name in METRICS}
        _require(
            all(isinstance(value, (int, float)) for value in values.values()),
            f"{path}: a turn is missing one of {METRICS}",
        )
        turns.append(
            (cast("str", question), {k: float(cast("float", v)) for k, v in values.items()})
        )
    _require(len(turns) > 0, f"{path}: sample holds no turns")
    return Block(path, cast("str", arm), tuple(turns))


def by_question(block: Block, metric: str) -> dict[str, float]:
    """The block's mean of ``metric`` for each question it asked."""
    grouped: dict[str, list[float]] = {}
    for question, values in block.turns:
        grouped.setdefault(question, []).append(values[metric])
    return {question: statistics.fmean(seen) for question, seen in grouped.items()}


def summarize(block: Block, metric: str) -> Summary:
    """Mean, median and standard deviation of every turn in the block, unblocked."""
    values = [turn[metric] for _, turn in block.turns]
    sd = statistics.stdev(values) if len(values) > 1 else 0.0
    return Summary(len(values), statistics.fmean(values), statistics.median(values), sd)


def differences(baseline: Block, arm: Block, metric: str) -> list[float]:
    """Per-question ``arm - baseline`` means, refusing two blocks that asked different questions."""
    left = by_question(baseline, metric)
    right = by_question(arm, metric)
    _require(
        set(left) == set(right),
        f"{baseline.path} and {arm.path} asked different questions, so they cannot be paired",
    )
    return [right[question] - left[question] for question in sorted(left)]


def percentile(ordered: list[float], fraction: float) -> float:
    """Linearly interpolated percentile of an already-sorted sample."""
    if len(ordered) == 1:
        return ordered[0]
    position = fraction * (len(ordered) - 1)
    low = math.floor(position)
    high = math.ceil(position)
    if low == high:
        return ordered[low]
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def bootstrap(values: list[float], *, resamples: int, seed: int) -> Interval:
    """Percentile bootstrap of the mean, resampling ``values`` with replacement."""
    _require(len(values) > 0, "a contrast over no questions has no interval")
    rng = random.Random(seed)  # noqa: S311 -- a bootstrap resampler, not a security decision
    count = len(values)
    means = sorted(statistics.fmean(rng.choices(values, k=count)) for _ in range(resamples))
    return Interval(
        statistics.fmean(values), percentile(means, LOW_TAIL), percentile(means, HIGH_TAIL)
    )


def report(blocks: list[Block], *, resamples: int, seed: int) -> str:
    """The whole reading: each block's shape, then each later block against the first."""
    lines = [f"blocks: {len(blocks)}, resamples: {resamples}, seed: {seed}", "", "per block:"]
    for block in blocks:
        shapes = "  ".join(
            f"{metric} mean {(s := summarize(block, metric)).mean:.3f}s"
            f" median {s.median:.3f}s sd {s.sd:.3f}s"
            for metric in METRICS
        )
        lines.append(f"  {block.arm} ({block.path.name}, n={len(block.turns)}): {shapes}")
    baseline = blocks[0]
    lines.extend(["", f"against the baseline block {baseline.arm} ({baseline.path.name}):"])
    for block in blocks[1:]:
        for metric in METRICS:
            interval = bootstrap(
                differences(baseline, block, metric), resamples=resamples, seed=seed
            )
            lines.append(
                f"  {block.arm} ({block.path.name}) {metric}: {interval.point:+.3f}s"
                f" (95% CI {interval.low:+.3f} to {interval.high:+.3f})"
                f"{'' if interval.low <= 0 <= interval.high else ' *'}"
            )
    lines.extend(["", "* an interval that does not span zero.", "", *_per_question(blocks)])
    return "\n".join(lines)


def _per_question(blocks: list[Block]) -> list[str]:
    """The blocking unit laid out, because one question can carry a whole contrast.

    The interval above is a mean over questions and says nothing about how evenly the arm's cost
    is spread across them. The first run of this harness found it very unevenly spread: one of six
    questions carried three times the mean difference, because the arm under test was the only one
    able to answer that it did not know, and a refusal takes longer to say than a wrong answer. A
    reader who sees only the interval cannot tell that from a uniform half second.
    """
    baseline = blocks[0]
    lines = [f"per question, {METRICS[0]} against {baseline.arm} ({baseline.path.name}):"]
    means = [by_question(block, METRICS[0]) for block in blocks]
    for question in sorted(means[0]):
        deltas = "  ".join(f"{seen[question] - means[0][question]:+.2f}s" for seen in means[1:])
        lines.append(f"  {means[0][question]:.2f}s  {deltas}  {question}")
    return lines


def main(argv: list[str] | None = None) -> int:
    """Read the sample files, print the report, and return the process exit code."""
    parser = argparse.ArgumentParser(
        description=(
            "Report each later block against the first, as a blocked paired bootstrap interval."
        ),
    )
    parser.add_argument("samples", type=Path, nargs="+", help="block sample files, baseline first")
    parser.add_argument("--resamples", type=int, default=DEFAULT_RESAMPLES)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    args = parser.parse_args(argv)
    samples = cast("list[Path]", args.samples)
    resamples = cast("int", args.resamples)
    seed = cast("int", args.seed)
    try:
        _require(len(samples) > 1, "a contrast needs a baseline block and at least one other")
        _require(resamples > 0, "a bootstrap needs at least one resample")
        print(report([load(path) for path in samples], resamples=resamples, seed=seed))
    except ContrastError as err:
        print(f"contrast: {err}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":  # pragma: no cover -- CLI entry point; main() is unit-tested
    sys.exit(main())
