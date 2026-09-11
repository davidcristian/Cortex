"""The per-condition sample file an envelope measurement writes, read as a set of runs."""

import json
from pathlib import Path
from typing import NamedTuple, cast

from envelopejudges import copied, declared, reduced


class FloorError(Exception):
    """A sample file is unreadable, malformed, or written by a driver too old to record a run."""


class Turn(NamedTuple):
    """One run of one condition, in the four things a lapse or a delivery can be read from."""

    instruction: str
    context: str
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
        if declared(self.instruction) is not None and copied(self.output, self.context):
            return "copy"
        return None


class Arm(NamedTuple):
    """One condition's sample: where it came from, what it was, and whether it is the control."""

    path: Path
    name: str
    control: bool
    turns: tuple[Turn, ...]


def _require(condition: bool, message: str) -> None:  # noqa: FBT001 -- a bare predicate is the point
    if not condition:
        raise FloorError(message)


def _text(source: dict[str, object], key: str, where: Path) -> str:
    """One string field of a sample; raises naming the file and the key when it is absent."""
    value = source.get(key)
    _require(isinstance(value, str), f"{where}: {key} is missing or is not a string")
    return cast("str", value)


def _flag(source: dict[str, object], key: str, where: Path) -> bool:
    """One boolean field of a sample; raises naming the file and the key when it is absent."""
    value = source.get(key)
    _require(isinstance(value, bool), f"{where}: {key} is missing or is not a boolean")
    return cast("bool", value)


def _turn(entry: object, where: Path) -> Turn:
    """One turn of a sample, raising on a run written before the driver recorded what it asked."""
    _require(isinstance(entry, dict), f"{where}: a turn is not a JSON object")
    turn = cast("dict[str, object]", entry)
    return Turn(
        _text(turn, "instruction", where),
        _text(turn, "context", where),
        _flag(turn, "ok", where),
        _text(turn, "output", where),
    )


def _number(source: dict[str, object], key: str, where: Path) -> int | None:
    """One integer field of a sample, which the driver writes as null when it has none."""
    _require(key in source, f"{where}: {key} is missing")
    value = source[key]
    whole = isinstance(value, int) and not isinstance(value, bool)
    _require(value is None or whole, f"{where}: {key} is not an integer or null")
    return cast("int | None", value)


def _parsed(path: Path) -> tuple[str, bool, list[object]]:
    """A sample's condition, whether it is the control, and its turns, raising on anything else."""
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
    return name, control, entries


def load(path: Path) -> Arm:
    """Read one condition's sample file, raising on anything it cannot read as a set of runs."""
    name, control, entries = _parsed(path)
    return Arm(path, name, control, tuple(_turn(entry, path) for entry in entries))


class Cell(NamedTuple):
    """One run as a paired reading matches it: where it sits, what it was asked, what it drew."""

    question: str
    draw: int | None
    seed: int | None
    asked: tuple[str, str]
    output: str
    tokens: int | None


def _cell(entry: object, where: Path) -> Cell:
    """One turn read for pairing: its place, its instruction and body, and its completion."""
    turn = _turn(entry, where)
    source = cast("dict[str, object]", entry)
    return Cell(
        _text(source, "question", where),
        _number(source, "draw", where),
        _number(source, "seed", where),
        (turn.instruction, turn.context),
        turn.output,
        _number(source, "tokens", where),
    )


def cells(path: Path) -> tuple[str, tuple[Cell, ...]]:
    """Read one condition's sample as the cells a paired reading matches, with its name."""
    name, _, entries = _parsed(path)
    return name, tuple(_cell(entry, path) for entry in entries)
