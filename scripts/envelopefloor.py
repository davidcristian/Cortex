"""Whether an envelope measurement's control condition still holds, and what it allows."""

import argparse
import math
import sys
from pathlib import Path
from typing import NamedTuple, cast

from envelopejudges import COMMAS, NAMINGS, REFUSALS, TABLED, Reading, delivered
from envelopesamples import Arm, FloorError, Turn, load

FLOOR = 0.9
# The two-sided 95% normal quantile, which is the interval every rate in the reply-envelope
# readings is published with.
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
        """The delivered half of the line a cell or a condition is reported as."""
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
        """The one line a cell or a condition is reported as."""
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
    """The Wilson 95% score interval on ``stood`` of ``runs``."""
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
    """The runs grouped by the instruction they were given, in the order the sample lists them."""
    grouped: dict[str, list[Turn]] = {}
    for turn in turns:
        grouped.setdefault(turn.instruction, []).append(turn)
    return {instruction: tuple(seen) for instruction, seen in grouped.items()}


def _control_cells(arms: list[Arm]) -> dict[str, tuple[Turn, ...]]:
    """Every control run in these samples, grouped by the subtask shape it was given."""
    control = tuple(turn for arm in arms if arm.control for turn in arm.turns)
    return shapes(control)


def _refusals(cells: dict[str, tuple[Turn, ...]], rates: dict[str, Rate]) -> list[str]:
    """One refusal line per control cell whose rate was proven under the floor."""
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
    """The report and the exit code: the control first, and the comparison only if it holds."""
    cells = _control_cells(arms)
    lines = [
        f"{len(arms)} arm sample(s): {', '.join(sorted({arm.name for arm in arms}))}",
        f"delivered read under: {reading.rendered()}; every floor held under {TABLED.rendered()}",
        "",
        "the control arm, per subtask shape (stood = accepted, not empty, not the ask or the"
        " body handed back; delivered = judged against the shape, where a judge is declared for"
        " it):",
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
