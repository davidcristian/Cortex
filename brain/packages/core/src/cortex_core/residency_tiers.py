"""Which peers of the cortex the standing residency is missing right now (ADR-0030 decision 4).

The standing residency is the cortex **plus** every tier a handoff evicts for the deep model's
sake, and putting those peers back is deliberately best effort: a tier that will not come back
must not be reported as the cortex being gone, so ``residency_moves.restart_evicted`` logs a
``ModelHostError`` and swallows it. What that leaves is the case this module exists for. The
cortex is serving, one peer is not, and the conductor reopens subagent admission the moment the
restore returns, so the next GPU-placed spawn is sent to a ``llama-server`` nothing restarted.

**Two paths write it, for one reason.** The swap back's restart is one; boot recovery's
convergence (``swap_recovery.py``), which ends in that same move, is the other, and it reaches
here from outside any handoff. The rule they share is what keeps them one record rather than two
opinions: the cortex's readiness is a statement about the cortex, and a peer that would not start
is a statement about the pool, whichever of the two asked.

**Missing is not the same as evicted, and only one of them is recorded here.** A tier stopped on
purpose while the deep model holds the card is not missing: it is exactly where the swap put it,
the pool is drained around it, and the card's arithmetic is corrected by ``residency_charge.py``
instead. A tier is missing only when the host was **asked** to run it and would not, which is why
the one writer is the restart's failure branch and why a swap in never touches this record. The
two read apart on the seam as well: a report that is not serving describes a swap in flight and
carries the swap's own words, while the note below can only ever ride a report that says the
usual assistant is up, so "a peer is down" and "everything is mid handoff" are never the same
sentence.

**What being told costs the placer.** ``SubagentPlacer`` fit-tests a spawn onto the GPU and
overflows to the CPU, and while a peer is missing that fit test is answering about a server that
is not listening. So the placer is *told*, in the same voice ``charge_handoff`` uses, and it
closes GPU placement until the record is whole again. That is one bit for the whole card rather
than one per tier, deliberately: the brain has no declared mapping from a hosted tier id
(``CORTEX_SWAP_EVICT_MODELS``) to the subagent GPU endpoint a roster entry dials, and inventing
one now would be config with a single possible value. The record itself is per tier, because that
is what an operator has to read and what a retry has to act on; the lever it pulls is coarser than
the record it keeps, and the deferral for a deployment that evicts a tier the pool never places on
is recorded with this close.
"""

import logging

from cortex_core.errors import ModelHostError
from cortex_core.model_host import ModelHostState
from cortex_core.ports import ModelHost, SubagentPlacer
from cortex_core.residency_state import ResidencyReport

# What ``Health`` says while the cortex is serving and a peer of it is not. It rides a **serving**
# report, so the overlay renders it after "Brain ready" rather than after "The brain is not
# serving": turns work, delegation works, and the one thing that changed is where delegated work
# runs. Naming the tiers is the point of publishing it at all, since the operator's next move is
# to look at that tier in the model host's own roster, which is also why the sentence names the
# state and not the cause: a peer is recorded here by a swap back and by boot recovery alike, and
# a line that said "after a deep task" would be false on a brain that has never escalated.
TIERS_MISSING_DETAIL = (
    "the model host is not running {models}, so delegated work is running on the CPU"
)

_logger = logging.getLogger(__name__)


class StandingTiers:
    """The peers the standing residency is missing, plus the one consequence of being one.

    Held by ``SwappingModelManager``, which owns every other belief about residency, and handed
    the same ``placer`` the pool places against so that a record and the arithmetic it invalidates
    cannot drift apart. ``None`` is the deployment with no subagent pool: the record is still kept
    (the seam still says which tier is down) and there is simply nothing to close.

    Every method is synchronous and awaits nothing, which is what makes it safe without a lock:
    a coroutine's read-modify-write here runs to completion without interleaving, exactly as the
    placer's own ledger does.
    """

    def __init__(self, placer: SubagentPlacer | None = None) -> None:
        self._placer = placer
        self._missing: set[str] = set()

    @property
    def missing(self) -> tuple[str, ...]:
        """Every tier believed down, sorted, as a snapshot a retry pass may iterate and mutate."""
        return tuple(sorted(self._missing))

    @property
    def placer(self) -> SubagentPlacer | None:
        """The placer this record writes to, read back by the callers that also charge it.

        There is one placer per process and the residency scope has two things to tell it, which
        is one collaborator too many for the swap back's signature; handing the record around and
        reading the placer off it keeps the pair a pair without inventing a second reference to
        one object (``residency_restore.py`` is the caller this exists for).
        """
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
        """Record that ``model`` is back, and reopen the GPU once nothing at all is missing.

        Reopening is deliberately conditional on the **whole** record rather than on this one
        tier: the placer holds one bit for the card, so a second tier still down must keep it
        closed. Calling this for a tier that was never missing is a no-op in both halves.
        """
        self._missing.discard(model)
        if not self._missing and self._placer is not None:
            self._placer.open_gpu()

    def note_on(self, report: ResidencyReport) -> ResidencyReport:
        """The report a probe should see: unchanged, or a serving one that names what is down.

        Only a **serving** report is annotated, and that is the whole down-versus-evicted rule as
        code: mid handoff the peers are stopped on purpose and the report already says a swap is
        happening, so adding "a tier is down" there would be describing the swap twice and calling
        it a fault.
        """
        if not report.serving or not self._missing:
            return report
        return ResidencyReport(
            serving=True, detail=TIERS_MISSING_DETAIL.format(models=", ".join(self.missing))
        )


async def retry_missing(host: ModelHost, tiers: StandingTiers) -> None:
    """One pass over the missing tiers: ask what each is doing, and start the ones that are not.

    The clearing path the record owes. A mark nothing ever removes is a stack that degrades
    permanently on one transient failure, and the swap back is far too rare an event to be the
    only retry: escalation may not happen again for hours, and until it does every delegated run
    pays a wasted GPU attempt or, with this record in place, gives up the GPU entirely.

    Bounded by construction: at most one ``status`` and one ``start`` per missing tier, both
    already idempotent by the port's contract, and nothing here waits for a load. Readiness is
    observed on a later pass rather than gated inside this one, so a tier that takes minutes to
    load costs this pass nothing and reopens the GPU the moment a pass sees it serving.
    """
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
