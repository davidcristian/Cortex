"""What a probe is told about the GPU, and what boot publishes before the first one arrives."""

from cortex_core.residency_board import ResidencyBoard
from cortex_core.residency_pace import HandoffPace
from cortex_core.residency_state import (
    RESIDENCY_BOOT_FAILED,
    RESIDENCY_SERVING,
    ResidencyReport,
)
from cortex_core.residency_tiers import StandingTiers
from cortex_core.residency_watch import BootWatch


class ResidencyProbeMixin:
    """The reporting side of ``SwappingModelManager``: what it publishes, and what it reports."""

    _board: ResidencyBoard
    _boot: BootWatch
    _tiers: StandingTiers
    _pace: HandoffPace

    async def publish_boot_residency(self, *, serving: bool) -> None:
        """Replace the constructor's seed with what boot recovery actually observed."""
        await self._boot.seed()
        await self._board.publish_report(RESIDENCY_SERVING if serving else RESIDENCY_BOOT_FAILED)

    @property
    def standing_tiers(self) -> StandingTiers:
        """The peer tiers recorded as not serving, for boot recovery to write from outside."""
        return self._tiers

    @property
    def handoff_pace(self) -> HandoffPace:
        """How the last handoff ran, for the deep phase to write from outside a swap's objects."""
        return self._pace

    def residency(self) -> ResidencyReport:
        """What the GPU is serving right now, answered synchronously and without I/O."""
        return self._pace.note_on(self._tiers.note_on(self._board.report))
