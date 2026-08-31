"""How the last handoff ran, for as long as that is still true of now."""

from datetime import datetime, timedelta

from cortex_core.ports import Clock
from cortex_core.residency_state import ResidencyReport, with_note

# One hour: past that the note no longer describes now, so there is nothing left to say.
DEFAULT_SPILL_DWELL_S = 3600.0

SPILLED_PACE_DETAIL = (
    "the last deep task ran far slower than this deployment measured for it, so deep tasks are "
    "taking much longer than they should"
)


class HandoffPace:
    """Whether the last handoff kept its expected speed, and how long that stays true."""

    def __init__(self, clock: Clock, *, dwell_s: float = DEFAULT_SPILL_DWELL_S) -> None:
        if dwell_s <= 0:
            msg = f"HandoffPace dwell_s must be > 0, got {dwell_s}"
            raise ValueError(msg)
        self._clock = clock
        self._dwell = timedelta(seconds=dwell_s)
        self._spilled_at: datetime | None = None

    def note_pace(self, *, spilled: bool) -> None:
        """Record whether the handoff that just ended ran slower than the deployment measured."""
        self._spilled_at = self._clock.now() if spilled else None

    def note_on(self, report: ResidencyReport) -> ResidencyReport:
        """The report a probe should see: unchanged, or a serving one saying deep tasks are slow."""
        return with_note(report, SPILLED_PACE_DETAIL) if self._spill_stands() else report

    def _spill_stands(self) -> bool:
        """Whether the slow-handoff note still applies: written, not cleared, not yet expired."""
        if self._spilled_at is None:
            return False
        return self._clock.now() - self._spilled_at < self._dwell
