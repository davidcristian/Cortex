"""Whether an envelope measurement's control arm still stands, and the comparison it gates.

`brain/packages/orchestrator/tests/test_envelope_cost_live.py` measures what the reply envelope
costs a narrow subtask, running several shapes of one request over the same report bodies
(ADR-0028). Every rate it produces is read against the arm carrying no grammar and no appended
sentence: "the envelope costs this pick 24 of 96 answers" means something only while the same pick
over the same bodies answers them without it. That arm returned 96 of 96 on three picks of the
subagent row and the record began quoting it as a constant. Two later picks answered 93 and 92 of
96, both times because the pick failed the subtask rather than because the envelope took an answer
away, and nothing reported it: the driver asserts that the arms saw the same bodies and that every
run reported timings, so a control arm collapsed to 40 of 96 would leave the same tidy table behind
for somebody to price the envelope against.

This is the floor under it, and it lives here for the reason `contrast.py` and `trailwidth.py` do:
the arithmetic behind a published number belongs in a gated tool rather than in an
integration-marked driver no gate ever runs. The driver records what each run did, this module
turns those records into rates, and the refusal therefore lands where the comparison is published
rather than where it is measured. `envelopesamples.py` answers for the driver's file format.

Two rates describe one run and both are published here. What a run **stood** is the weaker of the
two: the runner accepted the run, the reply is not empty, and it is not the instruction handed
back, all three readable whatever was asked. What a reply **delivered** is judged against the
subtask by `envelopejudges.py`, which declares a judge per subtask shape and none for a shape
nobody declared one for, in which case a cell publishes `stood` alone and names the shape. Under
the reading the ADR-0028 tables are in, `stood` bounds `delivered` from above, so a narration or an
answer simply wrong is invisible to the first rate and counted by the second.

The floor is nine tenths of a cell's own runs, argued rather than drawn from a run, and the rule is
one-sided: a cell is refused only when the whole Wilson 95% interval on its rate lies under the
floor. Both rates are held to it, `delivered` only where a judge is declared, and both verdicts are
taken under the tabled reading whatever columns a reader asked to be shown. There is deliberately
no `--floor`. The ADR-0028 control-arm and judged-delivery addenda and
`docs/modules/repo-gates.md` argue all of it, and that interval is the same arithmetic the ADR-0028
tables publish beside every rate.

Reads the driver's own per-arm sample files, `just envelope-floor measurements/envelope-*.json`.
Exit 0 published the comparison, 1 refused to (no control arm in these samples, or one proven under
a floor), 2 could not read a sample.
"""

import argparse
import math
import sys
from pathlib import Path
from typing import NamedTuple, cast

from envelopejudges import COMMAS, NAMINGS, REFUSALS, TABLED, Reading, delivered
from envelopesamples import Arm, FloorError, Turn, load

# The fraction of its own runs a control arm must not be proven to have fallen under. Nine tenths
# is where a control stops doing better than the arms it exists to explain (ADR-0028).
FLOOR = 0.9
# The two-sided 95% normal quantile, which is the interval every rate in the ADR-0028 addenda is
# published with. Ten of those intervals were recomputed here when this landed and all ten agree.
Z = 1.959963984540054


class Delivery(NamedTuple):
    """What a set of runs delivered, over the runs a declared judge could read."""

    delivered: int
    judged: int
    low: float
    high: float

    @property
    def refused(self) -> bool:
        """Whether this set is *proven* under the floor, which is what a red here has to be."""
        return self.high < FLOOR

    def rendered(self) -> str:
        """The delivered half of the line a cell or an arm is reported as."""
        return f"delivered {self.delivered} of {self.judged} ({self.low:.2f} to {self.high:.2f})"


class Rate(NamedTuple):
    """What a set of runs did: how many stood, out of how many, and inside what interval."""

    stood: int
    runs: int
    low: float
    high: float
    lapses: tuple[tuple[str, int], ...]
    delivery: Delivery | None

    @property
    def refused(self) -> bool:
        """Whether this set is *proven* under the floor, which is what a red here has to be."""
        return self.high < FLOOR

    def rendered(self) -> str:
        """The one line a cell or an arm is reported as."""
        seen = ", ".join(f"{kind} {count}" for kind, count in self.lapses)
        judged = (
            self.delivery.rendered()
            if self.delivery is not None
            else "no judge is declared for this shape"
        )
        return (
            f"stood on {self.stood} of {self.runs} ({self.low:.2f} to {self.high:.2f}), {judged}"
            f"{', lapses: ' + seen if seen else ''}"
        )


def wilson(stood: int, runs: int) -> tuple[float, float]:
    """The Wilson 95% score interval on ``stood`` of ``runs``.

    The interval the ADR-0028 addenda publish beside every rate, and the one a proportion near a
    boundary needs: the normal approximation puts the ceiling of a 32 of 32 cell above 1 and its
    floor far below where anybody would defend it.
    """
    seen = stood / runs
    spread = 1 + Z * Z / runs
    centre = (seen + Z * Z / (2 * runs)) / spread
    half = Z * math.sqrt(seen * (1 - seen) / runs + Z * Z / (4 * runs * runs)) / spread
    return max(0.0, centre - half), min(1.0, centre + half)


def delivery(turns: tuple[Turn, ...], reading: Reading) -> Delivery | None:
    """What these runs delivered, or ``None`` when no run of them has a judge to be read by."""
    verdicts = [
        delivered(turn.instruction, turn.context, turn.output, ok=turn.ok, reading=reading)
        for turn in turns
    ]
    judged = [verdict for verdict in verdicts if verdict is not None]
    if not judged:
        return None
    low, high = wilson(sum(judged), len(judged))
    return Delivery(sum(judged), len(judged), low, high)


def rate(turns: tuple[Turn, ...], reading: Reading = TABLED) -> Rate:
    """What one set of runs did, with its interval, its lapses by kind, and what it delivered."""
    lapses: dict[str, int] = {}
    for turn in turns:
        if turn.lapse is not None:
            lapses[turn.lapse] = lapses.get(turn.lapse, 0) + 1
    stood = len(turns) - sum(lapses.values())
    low, high = wilson(stood, len(turns))
    counted = tuple(sorted(lapses.items()))
    return Rate(stood, len(turns), low, high, counted, delivery(turns, reading))


def shapes(turns: tuple[Turn, ...]) -> dict[str, tuple[Turn, ...]]:
    """The runs grouped by the instruction they were given, in the order the sample carried them.

    A subtask shape IS its instruction here, and the floor is held per shape rather than over the
    pool because that is the cell a reader prices: a pick that answers a summarization and cannot
    do an extraction has one arm at ceiling and one on the floor, and their average describes
    neither.
    """
    grouped: dict[str, list[Turn]] = {}
    for turn in turns:
        grouped.setdefault(turn.instruction, []).append(turn)
    return {instruction: tuple(seen) for instruction, seen in grouped.items()}


def _control_cells(arms: list[Arm]) -> dict[str, tuple[Turn, ...]]:
    """Every control run in these samples, grouped by the subtask shape it was given."""
    control = tuple(turn for arm in arms if arm.control for turn in arm.turns)
    return shapes(control)


def _refusals(cells: dict[str, tuple[Turn, ...]], rates: dict[str, Rate]) -> list[str]:
    """The refusal lines these control cells earned, one per rate that was proven under the floor.

    A verdict is taken under the tabled reading and never under the columns a reader asked for, so
    the delivered rate a cell is held to is the one the record's own rows are in.
    """
    held = {shape: delivery(turns, TABLED) for shape, turns in cells.items()}
    stood = [shape for shape, found in rates.items() if found.refused]
    short = [shape for shape, found in held.items() if found is not None and found.refused]
    lines: list[str] = []
    if stood:
        lines.append(
            f"refused: {len(stood)} of {len(rates)} control cell(s) stood on fewer than"
            f" {FLOOR:.0%} of their own runs, so what these arms differ by is the pick failing the"
            " subtask and not the envelope."
        )
    if short:
        lines.append(
            f"refused: {len(short)} of {len(rates)} control cell(s) delivered on fewer than"
            f" {FLOOR:.0%} of the runs a judge could read, so this control arm was asked the"
            " subtask and did not do it."
        )
    if lines:
        lines.append(
            "The samples are still on disk and price this pick; no rate in them prices the"
            " envelope."
        )
    return lines


def publish(arms: list[Arm], reading: Reading = TABLED) -> tuple[str, int]:
    """The report and the exit code: the control arm first, the comparison only if it stands."""
    cells = _control_cells(arms)
    lines = [
        f"{len(arms)} arm sample(s): {', '.join(sorted({arm.name for arm in arms}))}",
        f"delivered read under: {reading.rendered()}; every floor held under {TABLED.rendered()}",
        "",
        "the control arm, per subtask shape (stood = accepted, not empty, not the ask handed"
        " back; delivered = judged against the shape, where a judge is declared for it):",
    ]
    if not cells:
        lines.append("  none of these samples is the control arm")
        lines.append(
            "refused: nothing here is a comparison. Every rate this harness publishes is read"
            " against the arm carrying no grammar and no sentence, and this run drew none."
        )
        return "\n".join(lines), 1
    rates = {shape: rate(turns, reading) for shape, turns in cells.items()}
    lines.extend(f"  {found.rendered()}  {shape!r}" for shape, found in rates.items())
    under = _refusals(cells, rates)
    if under:
        lines.extend(under)
        return "\n".join(lines), 1
    lines.extend(["", "the comparison, per arm over every shape:"])
    lines.extend(f"  {arm.name:<12} {rate(arm.turns, reading).rendered()}" for arm in arms)
    return "\n".join(lines), 0


def main(argv: list[str] | None = None) -> int:
    """Read the samples, publish or refuse, and return the process exit code."""
    parser = argparse.ArgumentParser(
        description=(
            "Report an envelope measurement's control arm per subtask shape, and publish the"
            " comparison between its arms only while that control arm stands."
        ),
    )
    parser.add_argument("samples", type=Path, nargs="+", help="one envelope-<arm>.json per arm")
    parser.add_argument(
        "--comma", choices=COMMAS, default=TABLED.comma, help="how a comma between digits reads"
    )
    parser.add_argument(
        "--refusal", choices=REFUSALS, default=TABLED.refusal, help="how a refused run reads"
    )
    parser.add_argument(
        "--naming", choices=NAMINGS, default=TABLED.naming, help="how a named period reads"
    )
    args = parser.parse_args(argv)
    try:
        arms = [load(path) for path in cast("list[Path]", args.samples)]
    except FloorError as err:
        print(f"envelopefloor: {err}", file=sys.stderr)
        return 2
    reading = Reading(cast("str", args.comma), cast("str", args.refusal), cast("str", args.naming))
    report, code = publish(arms, reading)
    print(report)
    return code


if __name__ == "__main__":  # pragma: no cover -- CLI entry point; main() is unit-tested
    sys.exit(main())
