"""Which peer tiers of the cortex are not serving right now."""

from enum import Enum

from cortex_core.ports import SubagentPlacer
from cortex_core.residency_state import ResidencyReport, with_note

TIERS_MISSING_DETAIL = (
    "the model host is not running {models}, so delegated work is running on the CPU"
)


class TierFault(Enum):
    """Why a peer tier is not serving, in the two kinds that differ."""

    MISSING = "missing"
    UNHOSTED = "unhosted"


class BaselineTiers:
    """The peer tiers that are not serving, plus the one consequence: no GPU placement."""

    def __init__(self, placer: SubagentPlacer | None = None) -> None:
        self._placer = placer
        self._faults: dict[str, TierFault] = {}

    @property
    def missing(self) -> tuple[str, ...]:
        """Every tier recorded as down, sorted, whichever kind of fault it is."""
        return tuple(sorted(self._faults))

    @property
    def placer(self) -> SubagentPlacer | None:
        """The placer this record writes to, read back by the callers that also charge it."""
        return self._placer

    def fault_of(self, model: str) -> TierFault | None:
        """Why this tier is recorded as down, or ``None`` when it is recorded as serving."""
        return self._faults.get(model)

    def mark_missing(self, model: str) -> None:
        """Record that ``model`` is not serving, and stop placing spawns on the GPU."""
        self._faults[model] = TierFault.MISSING
        if self._placer is not None:
            self._placer.close_gpu()

    def mark_unhosted(self, model: str) -> None:
        """Record that this host's roster has no such tier, and stop placing spawns on the GPU."""
        self._faults[model] = TierFault.UNHOSTED
        if self._placer is not None:
            self._placer.close_gpu()

    def mark_serving(self, model: str) -> None:
        """Record that ``model`` is back, and reopen the GPU once nothing at all is missing."""
        self._faults.pop(model, None)
        if not self._faults and self._placer is not None:
            self._placer.open_gpu()

    def note_on(self, report: ResidencyReport) -> ResidencyReport:
        """The report a probe should see: unchanged, or a serving one that names what is down."""
        if not self._faults:
            return report
        return with_note(report, TIERS_MISSING_DETAIL.format(models=", ".join(self.missing)))
