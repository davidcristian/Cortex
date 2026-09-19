"""One reading of the GPU card a row was served on, and the run-log line that reports it.

A token total becomes a time only against the rate the card was giving, and that rate changes
between runs, so the harness takes a reading at the start and the end of every row.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from statistics import median

# ``clocks.sm`` is the driver's short name for ``clocks.current.sm``; ``clocks.current.graphics``
# is a different clock. The maximum is queried beside it so a line can state the ratio.
FIELDS = (
    "clocks.sm",
    "clocks.max.sm",
    "power.draw",
    "enforced.power.limit",
    "power.max_limit",
    "power.default_limit",
    "clocks_event_reasons.sw_power_cap",
)
QUERY = ("nvidia-smi", f"--query-gpu={','.join(FIELDS)}", "--format=csv,noheader,nounits")

PREFIX = "card reading"
START = "start"
END = "end"
OFF_CARD = "the row is served on the cpu"

_UNREAD = "n/a"


class NoReadingError(Exception):
    """The card was not read; the message is the reason the line prints instead of figures."""


@dataclass(frozen=True)
class CardReading:
    """The card's figures by query field, each as ``nvidia-smi`` printed it."""

    raw: Mapping[str, str]

    def number(self, name: str) -> float | None:
        """The field as a number, or None when the driver printed a marker such as ``[N/A]``."""
        try:
            return float(self.raw[name])
        except ValueError:
            return None

    def fraction(self, part: str, whole: str) -> float | None:
        """``part`` over ``whole``, or None when either is not a number or the whole is zero."""
        top, bottom = self.number(part), self.number(whole)
        if top is None or not bottom:
            return None
        return top / bottom

    def ratio(self, part: str, whole: str) -> str:
        """``part`` over ``whole`` to two places, or ``n/a`` when either does not divide."""
        value = self.fraction(part, whole)
        return _UNREAD if value is None else f"{value:.2f}"


def reading_of(returncode: int, stdout: str, stderr: str) -> CardReading | NoReadingError:
    """What one finished ``QUERY`` call reports: the reading, or why there is none."""
    if returncode:
        said = " ".join(f"{stderr} {stdout}".split()) or "no output"
        return NoReadingError(f"exit {returncode}, {said}")
    rows = [line for line in stdout.splitlines() if line.strip()]
    if len(rows) != 1:
        return NoReadingError(f"{len(rows)} devices reported, where a row is served on one")
    values = tuple(value.strip() for value in rows[0].split(","))
    if len(values) != len(FIELDS):
        return NoReadingError(f"{len(values)} values for {len(FIELDS)} fields, {rows[0].strip()}")
    return CardReading(dict(zip(FIELDS, values, strict=True)))


def render(moment: str, row: str, reading: CardReading | NoReadingError) -> str:
    """The run-log line for one reading taken at ``moment`` of ``row``."""
    head = f"  {PREFIX} at {moment} of {row}:"
    if isinstance(reading, NoReadingError):
        return f"{head} none, {reading}"
    ceiling = reading.ratio("enforced.power.limit", "power.max_limit")
    over_default = reading.ratio("enforced.power.limit", "power.default_limit")
    draw = reading.ratio("power.draw", "power.max_limit")
    clock = reading.ratio("clocks.sm", "clocks.max.sm")
    cap = reading.raw["clocks_event_reasons.sw_power_cap"]
    fields = " ".join(f"{name}={value}" for name, value in reading.raw.items())
    return (
        f"{head} ceiling {ceiling} of max and {over_default} of default, draw {draw} of max, "
        f"clock {clock} of max, sw power cap {cap}; {fields}"
    )


def render_serving(
    row: str, interval_s: float, readings: Sequence[CardReading | NoReadingError]
) -> str:
    """The run-log line summarizing the readings taken every ``interval_s`` while ``row`` served."""
    head = f"  {PREFIX}s every {interval_s:g} s while serving {row}: {len(readings)} taken"
    read = [reading for reading in readings if isinstance(reading, CardReading)]
    if not read:
        last = f", the last {readings[-1]}" if readings else ""
        return f"{head}, none read{last}"
    unread = len(readings) - len(read)
    ceiling = _spread(read, "enforced.power.limit", "power.max_limit")
    clock = _spread(read, "clocks.sm", "clocks.max.sm")
    capped = sum(r.raw["clocks_event_reasons.sw_power_cap"] == "Active" for r in read)
    return (
        f"{head}, {unread} unread; ceiling of max {ceiling}; clock of max {clock}; "
        f"sw power cap Active in {capped} of {len(read)}"
    )


def _spread(read: Sequence[CardReading], part: str, whole: str) -> str:
    """The lowest, median and highest of one ratio over the readings that report both fields."""
    values = [v for r in read if (v := r.fraction(part, whole)) is not None]
    if not values:
        return _UNREAD
    return f"lowest {min(values):.2f} median {median(values):.2f} highest {max(values):.2f}"
