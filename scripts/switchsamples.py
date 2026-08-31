"""What one run of the thinking-switch probe recorded, read off the sample it wrote.

The reader's half of a format two trees share. `brain/packages/inference/tests/
test_thinking_switch_live.py` sends one prompt four ways against a live llama-server, asks it
`POST /apply-template` for the prompt each of those requests renders to, writes one JSON sample per
tier and judges nothing, for the reason the envelope harness's driver computes no rates: the claim
a measurement publishes belongs in a gated file and not in an integration-marked driver no gate
ever runs. `switchtail.py` is that file and this is what it reads with.

Every field is required by name, which stands in for a suite that cannot exist. Nothing runs the
driver under a gate: it is integration-marked, so neither CI nor the coverage gate reads a line of
it, and a field it stopped writing would leave `switchtail.py` reading a default and publishing
a verdict about nothing. A sample missing a field, or naming one differently, or carrying a count
as a string, therefore raises naming the file and the key rather than producing a report with a
hole in it.

A sample holds the `model` and `endpoint` the run was pointed at and the `ask` it really
sent, which is what a tail is found after; `renderings`, one prompt with the switch and one
without; and `cells`, each one request shape drawn some number of times, carrying how many of those
draws deliberated. Which cell is which is read off the sample's own `constrained` and `switch`
flags rather than off a shape's name, so the two trees have to agree about the flags and never
about the word `envelope`.
"""

import json
from pathlib import Path
from typing import NamedTuple, cast


class ProbeError(Exception):
    """A sample file is unreadable, malformed, or written by a driver too old to carry a run."""


class Cell(NamedTuple):
    """One request shape, sent one way, and how many of its draws deliberated."""

    shape: str
    constrained: bool
    switch: bool
    draws: int
    deliberated: int

    @property
    def verdict(self) -> str:
        """What this cell says about the switch, in the probe's own three words."""
        if self.deliberated == 0:
            return "holds"
        if self.deliberated == self.draws:
            return "does nothing"
        return f"holds on {self.draws - self.deliberated} of {self.draws} draws"

    def rendered(self) -> str:
        """The one line a cell is reported as, which is a different sentence per arm.

        Only the arm that sent the switch has a verdict about it. The other arm is the control,
        whose job is to have deliberated, and printing "the switch does nothing" beside a request
        that sent no switch would say something the run never measured.
        """
        sent = "switch" if self.switch else "no switch"
        if self.switch:
            said = f"the switch {self.verdict}"
        else:
            fired = self.deliberated == self.draws
            said = "the control fired" if fired else "the control did NOT fire on every draw"
        return (
            f"{self.shape:<9} {sent:<9} deliberated on {self.deliberated} of {self.draws}   {said}"
        )


class Probe(NamedTuple):
    """One tier's run of the probe: what it was pointed at, what it rendered, what it measured."""

    path: Path
    model: str
    endpoint: str
    ask: str
    plain: str
    switched: str
    cells: tuple[Cell, ...]

    def prompt(self, *, switch: bool) -> str:
        """The prompt this tier rendered with the switch sent, or with it left alone."""
        return self.switched if switch else self.plain

    def cell(self, *, switch: bool) -> Cell | None:
        """The one constrained cell sent that way, if this sample carries exactly one."""
        found = [seen for seen in self.cells if seen.constrained and seen.switch is switch]
        return found[0] if len(found) == 1 else None


def _require(condition: bool, message: str) -> None:  # noqa: FBT001 -- a bare predicate is the point
    if not condition:
        raise ProbeError(message)


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


def _count(source: dict[str, object], key: str, where: Path) -> int:
    """One count field of a sample; raises naming the file and the key when it is absent."""
    value = source.get(key)
    _require(
        isinstance(value, int) and not isinstance(value, bool) and value >= 0,
        f"{where}: {key} is missing or is not a count",
    )
    return cast("int", value)


def _rows(sample: dict[str, object], key: str, where: Path) -> list[dict[str, object]]:
    """One non-empty list of objects out of a sample; raises naming the file and the key."""
    rows = sample.get(key)
    _require(isinstance(rows, list), f"{where}: {key} is missing or is not a list")
    entries = cast("list[object]", rows)
    _require(len(entries) > 0, f"{where}: {key} is empty")
    for entry in entries:
        _require(isinstance(entry, dict), f"{where}: an entry of {key} is not a JSON object")
    return cast("list[dict[str, object]]", entries)


def load(path: Path) -> Probe:
    """Read one tier's sample file, raising on anything it cannot read as a run of the probe."""
    try:
        parsed: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as err:
        msg = f"{path}: unreadable sample ({err})"
        raise ProbeError(msg) from err
    _require(isinstance(parsed, dict), f"{path}: a sample is a JSON object")
    sample = cast("dict[str, object]", parsed)
    # One prompt each way is what the probe renders, so a sample carrying anything else is
    # malformed rather than unpublishable: no run of it renders one prompt, or three.
    rendered = {
        _flag(row, "switch", path): _text(row, "prompt", path)
        for row in _rows(sample, "renderings", path)
    }
    _require(
        set(rendered) == {False, True},
        f"{path}: renderings must carry one prompt with the switch and one without",
    )
    return Probe(
        path=path,
        model=_text(sample, "model", path),
        endpoint=_text(sample, "endpoint", path),
        ask=_text(sample, "ask", path),
        plain=rendered[False],
        switched=rendered[True],
        cells=tuple(
            Cell(
                _text(row, "shape", path),
                _flag(row, "constrained", path),
                _flag(row, "switch", path),
                _count(row, "draws", path),
                _count(row, "deliberated", path),
            )
            for row in _rows(sample, "cells", path)
        ),
    )
