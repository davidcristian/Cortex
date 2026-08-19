"""How the last handoff ran, for as long as that is still a fact about now (ADR-0030)."""

from datetime import datetime, timedelta

from cortex_core.ports import Clock
from cortex_core.residency_state import ResidencyReport, with_note

# How long a spill note stands when no later handoff decides it. One hour, argued above: past it
# the note stops describing now, and the only honest thing left to say is nothing.
DEFAULT_SPILL_DWELL_S = 3600.0

SPILLED_PACE_DETAIL = (
    "the last deep task ran far slower than this deployment measured for it, so deep tasks are "
    "taking much longer than they should"
)


class HandoffPace:
    """Whether the last handoff held its pace, and how long that answer still describes now."""

    def __init__(self, clock: Clock, *, dwell_s: float = DEFAULT_SPILL_DWELL_S) -> None:
        if dwell_s <= 0:
            msg = f"HandoffPace dwell_s must be > 0, got {dwell_s}"
            raise ValueError(msg)
        self._clock = clock
        self._dwell = timedelta(seconds=dwell_s)
        self._spilled_at: datetime | None = None

    def note_pace(self, *, spilled: bool) -> None:
        """Record how the handoff that just ended ran: the ``PaceSink`` port, implemented."""
        self._spilled_at = self._clock.now() if spilled else None

    def note_on(self, report: ResidencyReport) -> ResidencyReport:
        """The report a probe should see: unchanged, or a serving one that says the card is tight.
        """
        return with_note(report, SPILLED_PACE_DETAIL) if self._spill_stands() else report

    def _spill_stands(self) -> bool:
        """Whether a spill note is standing: written, not since cleared, and not yet lapsed.

        The dwell is exclusive at its far end, so a note is done exactly when it has stood for the
        whole of it, which is the boundary the tests are written against.
        """
        if self._spilled_at is None:
            return False
        return self._clock.now() - self._spilled_at < self._dwell
