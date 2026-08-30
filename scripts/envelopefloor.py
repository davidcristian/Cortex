"""Whether an envelope measurement's control arm still stands, and the comparison it gates."""

import argparse
import json
import math
import sys
from pathlib import Path
from typing import NamedTuple, cast

# The fraction of its own runs a control arm must not be proven to have fallen under. Argued in
# full above; nine tenths is where a control stops outrunning the arms it is supposed to explain.
FLOOR = 0.9
# The two-sided 95% normal quantile, which is the interval every rate in the ADR-0028 addenda is
# published with. Ten of those intervals were recomputed here when this landed and all ten agree.
Z = 1.959963984540054


class FloorError(Exception):
    """A sample file is unreadable, malformed, or written by a driver too old to carry a run."""


class Turn(NamedTuple):
    """One run of one arm, in the three things a lapse can be read from."""

    instruction: str
    ok: bool
    output: str

    @property
    def lapse(self) -> str | None:
        """Which visible failure this run is, or ``None`` when nothing visible failed."""
        if not self.ok:
            return "refused"
        if not self.output.strip():
            return "empty"
        if reduced(self.output) == reduced(self.instruction):
            return "echo"
        return None


class Arm(NamedTuple):
    """One arm's sample: where it came from, what it was, and whether it is the control."""

    path: Path
    name: str
    control: bool
    turns: tuple[Turn, ...]


class Rate(NamedTuple):
    """What a set of runs did: how many stood, out of how many, and inside what interval."""

    stood: int
    runs: int
    low: float
    high: float
    lapses: tuple[tuple[str, int], ...]

    @property
    def refused(self) -> bool:
        """Whether this set is *proven* under the floor, which is what a red here has to be."""
        return self.high < FLOOR

    def rendered(self) -> str:
        """The one line a cell or an arm is reported as."""
        seen = ", ".join(f"{kind} {count}" for kind, count in self.lapses)
        return (
            f"stood on {self.stood} of {self.runs} ({self.low:.2f} to {self.high:.2f})"
            f"{', lapses: ' + seen if seen else ''}"
        )


def reduced(text: str) -> str:
    """``text`` as its letters and digits alone, folded for case."""
    return "".join(character for character in text.casefold() if character.isalnum())


def wilson(stood: int, runs: int) -> tuple[float, float]:
    """The Wilson 95% score interval on ``stood`` of ``runs``."""
    seen = stood / runs
    spread = 1 + Z * Z / runs
    centre = (seen + Z * Z / (2 * runs)) / spread
    half = Z * math.sqrt(seen * (1 - seen) / runs + Z * Z / (4 * runs * runs)) / spread
    return max(0.0, centre - half), min(1.0, centre + half)


def rate(turns: tuple[Turn, ...]) -> Rate:
    """What one set of runs did, with its interval and its lapses counted by kind."""
    lapses: dict[str, int] = {}
    for turn in turns:
        if turn.lapse is not None:
            lapses[turn.lapse] = lapses.get(turn.lapse, 0) + 1
    stood = len(turns) - sum(lapses.values())
    low, high = wilson(stood, len(turns))
    return Rate(stood, len(turns), low, high, tuple(sorted(lapses.items())))


def shapes(turns: tuple[Turn, ...]) -> dict[str, tuple[Turn, ...]]:
    """The runs grouped by the instruction they were given, in the order the sample carried them."""
    grouped: dict[str, list[Turn]] = {}
    for turn in turns:
        grouped.setdefault(turn.instruction, []).append(turn)
    return {instruction: tuple(seen) for instruction, seen in grouped.items()}


def _require(condition: bool, message: str) -> None:  # noqa: FBT001 -- a bare predicate is the point
    if not condition:
        raise FloorError(message)


def _text(source: dict[str, object], key: str, where: Path) -> str:
    """One string field of a sample, or a refusal naming the file and the key."""
    value = source.get(key)
    _require(isinstance(value, str), f"{where}: {key} is missing or is not a string")
    return cast("str", value)


def _flag(source: dict[str, object], key: str, where: Path) -> bool:
    """One boolean field of a sample, or a refusal naming the file and the key."""
    value = source.get(key)
    _require(isinstance(value, bool), f"{where}: {key} is missing or is not a boolean")
    return cast("bool", value)


def _turn(entry: object, where: Path) -> Turn:
    """One turn of a sample, refusing a run written before the driver recorded what it asked."""
    _require(isinstance(entry, dict), f"{where}: a turn is not a JSON object")
    turn = cast("dict[str, object]", entry)
    return Turn(
        _text(turn, "instruction", where),
        _flag(turn, "ok", where),
        _text(turn, "output", where),
    )


def load(path: Path) -> Arm:
    """Read one arm's sample file, refusing anything it cannot read as a set of runs."""
    try:
        parsed: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as err:
        msg = f"{path}: unreadable sample ({err})"
        raise FloorError(msg) from err
    _require(isinstance(parsed, dict), f"{path}: a sample is a JSON object")
    sample = cast("dict[str, object]", parsed)
    name = _text(sample, "arm", path)
    control = _flag(sample, "control", path)
    rows = sample.get("turns")
    _require(isinstance(rows, list), f"{path}: turns is missing or is not a list")
    entries = cast("list[object]", rows)
    _require(len(entries) > 0, f"{path}: the sample holds no turns")
    return Arm(path, name, control, tuple(_turn(entry, path) for entry in entries))


def _control_cells(arms: list[Arm]) -> dict[str, tuple[Turn, ...]]:
    """Every control run in these samples, grouped by the subtask shape it was given."""
    control = tuple(turn for arm in arms if arm.control for turn in arm.turns)
    return shapes(control)


def publish(arms: list[Arm]) -> tuple[str, int]:
    """The report and the exit code: the control arm first, the comparison only if it stands."""
    cells = _control_cells(arms)
    lines = [
        f"{len(arms)} arm sample(s): {', '.join(sorted({arm.name for arm in arms}))}",
        "",
        "the control arm, per subtask shape (stood = accepted, not empty, not the ask handed"
        " back; it bounds delivered from above and does not measure it):",
    ]
    if not cells:
        lines.append("  none of these samples is the control arm")
        lines.append(
            "refused: nothing here is a comparison. Every rate this harness publishes is read"
            " against the arm carrying no grammar and no sentence, and this run drew none."
        )
        return "\n".join(lines), 1
    rates = {shape: rate(turns) for shape, turns in cells.items()}
    lines.extend(f"  {found.rendered()}  {shape!r}" for shape, found in rates.items())
    under = [shape for shape, found in rates.items() if found.refused]
    if under:
        lines.append(
            f"refused: {len(under)} of {len(rates)} control cell(s) proven below {FLOOR:.0%} of"
            " their own runs, so what these arms differ by is the pick failing the subtask and"
            " not the envelope. The samples are still on disk and price this pick; no rate in"
            " them prices the envelope."
        )
        return "\n".join(lines), 1
    lines.extend(["", "the comparison, per arm over every shape:"])
    lines.extend(f"  {arm.name:<12} {rate(arm.turns).rendered()}" for arm in arms)
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
    args = parser.parse_args(argv)
    try:
        arms = [load(path) for path in cast("list[Path]", args.samples)]
    except FloorError as err:
        print(f"envelopefloor: {err}", file=sys.stderr)
        return 2
    report, code = publish(arms)
    print(report)
    return code


if __name__ == "__main__":  # pragma: no cover -- CLI entry point; main() is unit-tested
    sys.exit(main())
