"""Whether the daemon under this brain is the one its beliefs were formed against (ADR-0030).

The brain's residency bookkeeping is instance state: which model the GPU serves, what the seam
tells a human about it, and, read once at boot, whether the deadline this brain bounds a control
call with clears the worst stop the sidecar was configured for. All of it is formed against one
supervisor process, and all of it is void the moment that process is replaced, which the compose
restart policy does whenever the sidecar is killed, crashes, or is restarted by hand. The fresh
daemon starts its own boot default and is right about the machine; the brain is the one left
describing a child table that no longer exists.

So the daemon names its own boot on ``GET /health``, and this is the brain's half of that:
remember which daemon answered last, notice when a different one answers, and rebuild exactly what
the change invalidated. Two things were formed against that daemon, so two are rebuilt:

- **Residency.** ``converge_residency`` puts the machine back into the standing shape, which is
  boot recovery's own convergence reused rather than a second version of it, and what it observed
  is published, so the manager's beliefs and the seam's report are rewritten from one reading
  instead of being left to disagree with each other and with the GPU. The peer record is rewritten
  by that same convergence and for the same reason: which tiers were missing was a statement about
  a child table the replaced daemon took with it.
- **The deadline pairing.** The sidecar's stop bounds are its own environment, and a restart is
  the one event that can change them under a brain that never restarted. They are therefore read
  again here, and nowhere else in a swap, since nothing else can have moved them.

**Only a replacement does any of that**, which is why the seed exists. Converging is not free of
consequence: it stops and restarts every tier a swap is allowed to evict, and a co-resident plan
deliberately leaves those tiers alone, so a convergence run before every handoff would take down
peers that plan exists to keep serving. A first observation is therefore a seed and never a
change, and the boot publish seeds it, so the very first handoff already has a daemon to compare
against rather than a blank.
"""

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


class BootWatch:
    """The daemon this brain last spoke to, and what speaking to a different one costs.

    Held by ``SwappingModelManager``, which owns the beliefs at stake and is the only object that
    may rewrite them; the writer arrives as a ``ResidencyPublisher`` so this one never reaches
    into that state. ``tiers`` is the same arrangement for the peer record, handed in rather than
    reached for so a convergence run here writes what a swap back writes. ``seed`` records who
    answered when boot recovery finished, and ``reconcile`` is the comparison plus everything a
    difference implies.
    """

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
        """Whether ``boot_id`` is a **different** daemon from the last one that named itself.

        Three answers and only one of them is ``True``. A host that will not say (``None``) is no
        evidence in either direction, so what was remembered is kept rather than cleared: a daemon
        that named itself once and has gone quiet must not read as a restart when it speaks again.
        A first answer is a seed, because nothing was believed against anything before it. Anything
        else is a replacement, and it is remembered immediately, so one restart is reconciled once
        rather than at every handoff after it.
        """
        if boot_id is None:
            return False
        replaced = self._seen is not None and boot_id != self._seen
        self._seen = boot_id
        return replaced

    async def seed(self) -> None:
        """Record which daemon boot recovery just converged, so a later one can be told apart.

        Called from the boot publish, at the one moment the machine and the beliefs about it are
        known to agree. It only ever records: recovery has converged residency already, and the
        composition root has checked the deadline pairing already, so there is nothing here to
        rebuild even when the answer is a daemon this process has never seen.
        """
        self.observe(await self._named_boot())

    async def reconcile(self, publish: ResidencyPublisher) -> None:
        """Rebuild what a replaced daemon invalidated, or return having done nothing at all.

        The normal case is the second one: the same daemon is still answering, so this costs one
        ``GET /health`` and no decision. When the daemon has been replaced it raises
        ``SwapFailedError`` for either of the two conditions a handoff must not be started under,
        a machine that could not be converged and a deadline the fresh sidecar's stop can outlast.
        Both refusals leave the standing residency to the scope's own ``finally``, which is the
        recovery path every other swap failure already takes, and both happen before anything is
        evicted, so a refused handoff has unloaded nothing.
        """
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
        """Which daemon is answering, or ``None`` when it will not or cannot say.

        A host that cannot be asked is tolerated exactly as the composition root's pairing check
        tolerates one: nothing is observed, so nothing is rebuilt, and the beliefs stand. That is
        the honest reading of no answer, and it costs nothing here, because a swap whose host is
        unreachable fails at its very next move with the failure that really happened.
        """
        try:
            return await self._host.boot_id()
        except ModelHostError as err:
            _logger.warning(
                "the model host could not be asked which daemon is answering: error=%s",
                err,
                extra={"error": str(err)},
            )
            return None

    async def _converge(self, publish: ResidencyPublisher) -> None:
        """Put the machine back into the standing shape, and publish what that actually found.

        Success is the cortex **observed** serving, which is exactly what the fresh daemon's own
        boot default leaves behind, so the ordinary restart converges in two status calls and
        moves nothing. A convergence that could not confirm the cortex publishes that nothing is
        resident, and that is the one place this differs from the boot publish, which deliberately
        leaves the resident alone: at boot an unconfirmed cortex may still be serving and the
        seed is only an assumption, while here the beliefs are known to have been formed against
        a process that is gone, so keeping them would be asserting something already false.

        Success is the cortex, and a peer of it that the fresh daemon will not run is recorded
        instead of refusing the handoff: the deep model is about to be alone on the card anyway,
        so a delegation tier that is down changes where delegated work runs and nothing about
        whether this swap may proceed.
        """
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
        _logger.error(msg, extra={"model": self._plan.cortex_model})
        raise SwapFailedError(msg)

    async def _recheck_deadline(self) -> None:
        """Refuse a handoff whose fresh sidecar can outlast the deadline this brain bounds it with.

        The same rule the composition root refuses to serve on, asked again because this is the
        only event that can have changed either side of it. Refusing here rather than logging is
        the same judgement it makes: the mispairing's own failure is intermittent, since a stop
        pays the whole SIGTERM grace only when the tier it evicts was busy, so a handoff allowed
        to start under it would abort an eviction that was working. Refused before that eviction
        instead, the cortex is still serving and the user is told the handoff did not happen.

        The two tolerant answers are tolerated for the reasons they always were: a host that will
        not state its bounds bounds nothing this can compare against, and a deployment that
        declared no deadline of its own has stated no rule to check.
        """
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
        _logger.error(msg, extra={"deadline_s": deadline_s, "worst_s": bounds.worst_case_stop_s})
        raise SwapFailedError(msg)

    async def _bounds(self) -> ControlBounds | None:
        """The fresh daemon's own stop bounds, or ``None`` when it cannot be asked for them."""
        try:
            return await self._host.control_bounds()
        except ModelHostError as err:
            _logger.warning(
                "the model host could not be asked for its control bounds after a restart, so "
                "the deadline pairing is unchecked: error=%s",
                err,
                extra={"error": str(err)},
            )
            return None
