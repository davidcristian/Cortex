"""Which peers of the cortex the standing residency is missing right now (ADR-0030 decision 4)."""

import logging

from cortex_core.errors import ModelHostError
from cortex_core.model_host import ModelHostState
from cortex_core.ports import ModelHost, SubagentPlacer
from cortex_core.residency_state import ResidencyReport

TIERS_MISSING_DETAIL = (
    "the model host is not running {models}, so delegated work is running on the CPU"
)

_logger = logging.getLogger(__name__)


class StandingTiers:
    """The peers the standing residency is missing, plus the one consequence of being one."""

    def __init__(self, placer: SubagentPlacer | None = None) -> None:
        self._placer = placer
        self._missing: set[str] = set()

    @property
    def missing(self) -> tuple[str, ...]:
        """Every tier believed down, sorted, as a snapshot a retry pass may iterate and mutate."""
        return tuple(sorted(self._missing))

    @property
    def placer(self) -> SubagentPlacer | None:
        """The placer this record writes to, read back by the callers that also charge it."""
        return self._placer

    def mark_missing(self, model: str) -> None:
        """Record that the host **refused** to run ``model``, and stop placing spawns on the GPU.

        Refused, never merely stopped: this is called where a ``start`` raised, from the swap
        back's restart and from boot recovery's convergence, and from nowhere else.
        """
        self._missing.add(model)
        if self._placer is not None:
            self._placer.close_gpu()

    def mark_standing(self, model: str) -> None:
        """Record that ``model`` is back, and reopen the GPU once nothing at all is missing."""
        self._missing.discard(model)
        if not self._missing and self._placer is not None:
            self._placer.open_gpu()

    def note_on(self, report: ResidencyReport) -> ResidencyReport:
        """The report a probe should see: unchanged, or a serving one that names what is down."""
        if not report.serving or not self._missing:
            return report
        return ResidencyReport(
            serving=True, detail=TIERS_MISSING_DETAIL.format(models=", ".join(self.missing))
        )


async def retry_missing(host: ModelHost, tiers: StandingTiers) -> None:
    """One pass over the missing tiers: ask what each is doing, and start the ones that are not."""
    for model in tiers.missing:
        await _retry_one(host, model, tiers)


async def _retry_one(host: ModelHost, model: str, tiers: StandingTiers) -> None:
    """Retry one missing tier, and never raise: a pass that dies stops retrying the others."""
    try:
        state = await host.status(model)
        if state is ModelHostState.READY:
            tiers.mark_standing(model)
            _logger.info(
                "a tier the standing residency was missing is serving again", extra={"model": model}
            )
            return
        if state is ModelHostState.LOADING:
            # It is on its way. Starting it again would be a no-op at the supervisor, and saying
            # anything about it would be saying the same thing every pass for the whole load.
            return
        await host.start(model)
    except ModelHostError as err:
        _logger.warning(
            "a tier the standing residency is missing could not be retried: model=%s error=%s",
            model,
            err,
            extra={"model": model, "error": str(err)},
        )
