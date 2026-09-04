"""The per-arm sample file an envelope measurement writes, read as a set of runs (ADR-0028)."""

import json
from pathlib import Path
from typing import NamedTuple, cast

from envelopejudges import reduced


class FloorError(Exception):
    """A sample file is unreadable, malformed, or written by a driver too old to carry a run."""


class Turn(NamedTuple):
    """One run of one arm, in the four things a lapse or a delivery can be read from."""

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
        return None


class Arm(NamedTuple):
    """One arm's sample: where it came from, what it was, and whether it is the control."""

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


def load(path: Path) -> Arm:
    """Read one arm's sample file, raising on anything it cannot read as a set of runs."""
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
