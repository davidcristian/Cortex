"""Whether the daemon under this brain is the one its state was built against."""

import logging

from cortex_core.errors import ModelHostError, SwapFailedError
from cortex_core.model_host import ControlBounds, ResidencyPlan
from cortex_core.ports import Clock, ModelHost, Sleeper
from cortex_core.residency_state import (
    RESIDENCY_LOST,
    RESIDENCY_SERVING,
    ResidencyPublisher,
)
from cortex_core.residency_tiers import StandingTiers
from cortex_core.swap_recovery import converge_residency

_logger = logging.getLogger(__name__)

_NOT_CONVERGED = "the model host was replaced and residency could not be converged onto the cortex"
_WORST_STOP_UNCLEARED = "the fresh model host's worst stop is no longer cleared by the deadline"


class BootWatch:
    """The daemon this brain last spoke to, and what changes when a different one answers."""

    def __init__(
        self,
        host: ModelHost,
        plan: ResidencyPlan,
        tiers: StandingTiers,
        *,
        clock: Clock,
        sleeper: Sleeper,
    ) -> None:
        self._host = host
        self._plan = plan
        self._tiers = tiers
        self._clock = clock
        self._sleeper = sleeper
        self._seen: str | None = None

    def observe(self, boot_id: str | None) -> bool:
        """Whether ``boot_id`` is a different daemon from the last one that named itself."""
        if boot_id is None:
            return False
        replaced = self._seen is not None and boot_id != self._seen
        self._seen = boot_id
        return replaced

    async def seed(self) -> None:
        """Record which daemon boot recovery just converged, so a later one can be told apart."""
        self.observe(await self._named_boot())

    async def reconcile(self, publish: ResidencyPublisher) -> None:
        """Rebuild what a replaced daemon invalidated, or return having done nothing at all."""
        if not self.observe(await self._named_boot()):
            return
        _logger.warning(
            "the model host has been replaced since the last handoff; reconciling residency "
            "against the daemon that is answering now",
            extra={"boot_id": self._seen},
        )
        await self._converge(publish)
        await self._recheck_deadline()

    async def _named_boot(self) -> str | None:
        """Which daemon is answering, or ``None`` when it will not or cannot say."""
        try:
            return await self._host.boot_id()
        except ModelHostError as err:
            _logger.warning(
                "the model host could not be asked which daemon is answering",
                extra={"error": str(err)},
            )
            return None

    async def _converge(self, publish: ResidencyPublisher) -> None:
        """Put the machine back into its usual residency, and publish what that actually found."""
        if await converge_residency(
            self._host, self._plan, self._tiers, clock=self._clock, sleeper=self._sleeper
        ):
            await publish(self._plan.cortex_model, RESIDENCY_SERVING)
            return
        await publish(None, RESIDENCY_LOST)
        msg = (
            "the model host was replaced and residency could not be converged onto "
            f"{self._plan.cortex_model!r} again, so the handoff was not started and nothing was "
            "unloaded (docs/runbooks/model-swap.md)"
        )
        _logger.error(_NOT_CONVERGED, extra={"model": self._plan.cortex_model})
        raise SwapFailedError(msg)

    async def _recheck_deadline(self) -> None:
        """Raise when the new sidecar's slowest stop is longer than the deadline this brain sets."""
        deadline_s = self._plan.control_deadline_s
        bounds = await self._bounds()
        if bounds is None or deadline_s <= 0 or bounds.clears(deadline_s):
            return
        msg = (
            f"the model host came back with a worst stop of {bounds.worst_case_stop_s} s (probe "
            f"{bounds.probe_timeout_s} s, grace {bounds.stop_grace_s} s, reap "
            f"{bounds.reap_timeout_s} s), which CORTEX_MODELHOST_TIMEOUT_S of {deadline_s} s no "
            "longer clears, so an eviction that was working would time out mid handoff; the "
            "handoff was not started and nothing was unloaded (docs/runbooks/model-swap.md)"
        )
        _logger.error(_WORST_STOP_UNCLEARED, extra=bounds.pairing_fields(deadline_s))
        raise SwapFailedError(msg)

    async def _bounds(self) -> ControlBounds | None:
        """The fresh daemon's own stop bounds, or ``None`` when it cannot be asked for them."""
        try:
            return await self._host.control_bounds()
        except ModelHostError as err:
            _logger.warning(
                "the model host could not be asked for its control bounds after a restart, so "
                "the deadline pairing is unchecked",
                extra={"error": str(err)},
            )
            return None
