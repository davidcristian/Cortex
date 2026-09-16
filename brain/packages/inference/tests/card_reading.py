"""One reading of the card a row is served on, and the run-log line that carries it."""

from collections.abc import Mapping
from dataclasses import dataclass

# The SM clock is the clock ADR-0029's addenda publish, and its maximum is queried beside it so
# the line can state it as a ratio. ``clocks.sm`` is the driver's short name for
# ``clocks.current.sm``; ``clocks.current.graphics`` is a different clock.
FIELDS = (
    "clocks.sm",
    "clocks.max.sm",
    "power.draw",
    "enforced.power.limit",
    "power.max_limit",
    "power.default_limit",
    "clocks_event_reasons.sw_power_cap",
)
# No header and no units, so a row is exactly one value per field.
QUERY = ("nvidia-smi", f"--query-gpu={','.join(FIELDS)}", "--format=csv,noheader,nounits")

# Every line this module renders starts with this, so one grep finds every reading in a run log.
PREFIX = "card reading at"
START = "start"
END = "end"
# The reason a CPU row's line gives: its container has no device reserved, so no binary either.
OFF_CARD = "the row is served on the cpu"

# What a ratio prints when either side is not a number, or the whole is zero.
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

    def ratio(self, part: str, whole: str) -> str:
        """``part`` over ``whole`` to two places, or ``n/a`` when either does not divide."""
        top, bottom = self.number(part), self.number(whole)
        if top is None or not bottom:
            return _UNREAD
        return f"{top / bottom:.2f}"


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
    """The run-log line for one reading taken at ``moment`` of ``row``.

    Ratios first, since those are what a price is published against, then every field as
    printed, so a later reader can recompute a ratio the line does not state.
    """
    head = f"  {PREFIX} {moment} of {row}:"
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
