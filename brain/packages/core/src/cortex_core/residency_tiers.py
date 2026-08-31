"""Which peers of the cortex the standing residency is missing right now (ADR-0030 decision 4).

The standing residency is the cortex plus every tier a handoff evicts for the deep model's sake,
and putting those peers back is deliberately best effort: a tier that will not come back must not
be reported as the cortex being gone, so ``residency_moves.restart_evicted`` logs a
``ModelHostError`` and continues. That leaves the case this module exists for. The cortex is
serving, one peer is not, and the conductor reopens subagent admission the moment the restore
returns, so the next GPU-placed spawn goes to a ``llama-server`` nothing restarted.

Three passes write the record, and share one rule that keeps them one record rather than three
opinions: the cortex's readiness is a statement about the cortex, and a peer that is not serving is
a statement about the pool, whichever pass looked. They are the swap back's restart; boot recovery's
convergence (``swap_recovery.py``), which ends in that same move from outside any handoff; and the
sweep (``residency_sweep.py``), which reaches it from outside a handoff too and with no failed start
to go on, being a reading of what the host says every tier is doing.

Missing is not the same as evicted, and only missing is recorded here. A tier stopped on purpose
while the deep model holds the card is where the swap put it, the pool is drained around it, and
the card's arithmetic is corrected by ``residency_charge.py`` instead. The two are kept apart by
when this record may be written rather than by what writes it (ADR-0030 tier-sweep addendum): no
pass runs while a handoff owns the GPU, and by the time a scope ends the restart has already asked
every peer to come back, so a reading never sees an eviction. They stay apart on the seam as well,
since the note below is added only to a report that says the cortex is serving, while a report
about a swap in flight carries the swap's own text.

The placer is written to as well as the record, because ``SubagentPlacer`` fit-tests a spawn onto
the GPU and overflows to the CPU, and while a peer is missing that fit test describes a server that
is not listening. It holds one bit for the whole card rather than one per tier, deliberately: the
brain has no declared mapping from a hosted tier id (``CORTEX_SWAP_EVICT_MODELS``) to the subagent
GPU endpoint a roster entry dials, and inventing one now would be config with a single possible
value. The record itself is per tier, since that is what an operator reads and what a retry acts
on. A deployment that evicts a tier the pool never places on is a recorded refinement.
"""

from enum import Enum

from cortex_core.ports import SubagentPlacer
from cortex_core.residency_state import ResidencyReport, with_note

# What ``Health`` says while the cortex is serving and a peer of it is not. It is added only to a
# serving report, so the overlay renders it after "Brain ready" rather than after "The brain is not
# serving": turns work, delegation works, and the one thing that changed is where delegated work
# runs. The tiers are named because the operator's next move is to look at that tier in the model
# host's own roster. The sentence names the state rather than the cause, since a peer is recorded
# here by a swap back and by boot recovery alike, and a line that said "after a deep task" would be
# false on a brain that has never escalated.
TIERS_MISSING_DETAIL = (
    "the model host is not running {models}, so delegated work is running on the CPU"
)


class TierFault(Enum):
    """Why a peer of the standing residency is not serving, in the two kinds that differ.

    ``MISSING`` is a condition that heals: the tier was asked to run and would not, or a reading
    found it stopped or failed, and another ``start`` may well succeed. ``UNHOSTED`` is the port's
    ``ModelNotHostedError`` written down: this daemon builds its roster from its own env once at
    boot, so it has no such id and will not grow one, and asking again spends a control call on a
    question whose answer cannot change. The one event that can change it, a daemon replaced under
    this brain, rebuilds the whole record through ``residency_watch.py``.

    Both close GPU placement, there being no server to place on either way, which is the only thing
    the placer's one bit can express. They differ in one place, the sweep, which retries the first
    and skips the second.
    """

    MISSING = "missing"
    UNHOSTED = "unhosted"


class StandingTiers:
    """The peers the standing residency is missing, plus the one consequence of being one.

    Held by ``SwappingModelManager``, which owns every other piece of residency state, and handed
    the same ``placer`` the pool places against so that a record and the arithmetic it invalidates
    cannot drift apart. ``None`` is the deployment with no subagent pool: the record is still kept
    (the seam still says which tier is down) and there is nothing to close.

    Every method is synchronous and awaits nothing, which is what makes it safe without a lock: a
    coroutine's read-modify-write here runs to completion without interleaving, as the placer's own
    ledger does.
    """

    def __init__(self, placer: SubagentPlacer | None = None) -> None:
        self._placer = placer
        self._faults: dict[str, TierFault] = {}

    @property
    def missing(self) -> tuple[str, ...]:
        """Every tier recorded as down, sorted, whichever kind of fault it is.

        One list because the two kinds have one consequence: the placer closes on either and the
        seam names either, and "the model host is not running X" is true whether the daemon lost
        that child or never had it. The sweep is the one reader that needs the difference, and it
        reads ``fault_of`` rather than this.
        """
        return tuple(sorted(self._faults))

    @property
    def placer(self) -> SubagentPlacer | None:
        """The placer this record writes to, read back by the callers that also charge it.

        There is one placer per process and the residency scope has two things to tell it, which
        is one collaborator too many for the swap back's signature; handing the record around and
        reading the placer off it keeps the pair a pair without inventing a second reference to
        one object (``residency_restore.py`` is the caller this exists for).
        """
        return self._placer

    def fault_of(self, model: str) -> TierFault | None:
        """Why this tier is recorded as down, or ``None`` when it is recorded as standing.

        The one reader that needs the kind rather than the list is the sweep, which must not spend
        a control call on a roster that cannot grow.
        """
        return self._faults.get(model)

    def mark_missing(self, model: str) -> None:
        """Record that ``model`` is not serving, and stop placing spawns on the GPU.

        Written where a ``start`` raised (the swap back's restart, boot recovery's convergence) and
        where a reading outside any handoff found the tier stopped or failed (the sweep). Never
        where a swap deliberately stopped it: what keeps that true is the sweep's fence rather than
        this method, since a pass does not run while a handoff owns the GPU.
        """
        self._faults[model] = TierFault.MISSING
        if self._placer is not None:
            self._placer.close_gpu()

    def mark_unhosted(self, model: str) -> None:
        """Record that this host's roster has no such tier, and stop placing spawns on the GPU.

        The same consequence as ``mark_missing``, with one difference: nothing retries it, because
        nothing this brain can do makes a daemon serve an id its own env never named. A replacement
        daemon is the one thing that can, and it rebuilds this record wholesale.
        """
        self._faults[model] = TierFault.UNHOSTED
        if self._placer is not None:
            self._placer.close_gpu()

    def mark_standing(self, model: str) -> None:
        """Record that ``model`` is back, and reopen the GPU once nothing at all is missing.

        Reopening is deliberately conditional on the **whole** record rather than on this one
        tier: the placer holds one bit for the card, so a second tier still down must keep it
        closed. Calling this for a tier that was never missing is a no-op in both halves.
        """
        self._faults.pop(model, None)
        if not self._faults and self._placer is not None:
            self._placer.open_gpu()

    def note_on(self, report: ResidencyReport) -> ResidencyReport:
        """The report a probe should see: unchanged, or a serving one that names what is down.

        Only a **serving** report is annotated, and that is the whole down-versus-evicted rule as
        code: mid handoff the peers are stopped on purpose and the report already says a swap is
        happening, so adding "a tier is down" there would be describing the swap twice and calling
        it a fault. That half of the rule is ``residency_state.with_note``, shared with the other
        annotator of a serving report (``residency_pace.py``) since neither may speak over a swap.
        """
        if not self._faults:
            return report
        return with_note(report, TIERS_MISSING_DETAIL.format(models=", ".join(self.missing)))
