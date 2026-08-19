"""What a probe is told about the GPU, and what boot publishes before the first one arrives.

Split from ``residency.py`` along the seam that module's docstring already draws between owning
the GPU and being honest about it: ``residency_board.py`` owns the bookkeeping a swap publishes
into, ``residency_moves.py`` owns what the host is asked to do, and this owns **the answer a
reader gets**, which is a different thing from the record because it is composed rather than
stored. ``SwappingModelManager`` mixes it in, the way ``BrainService`` mixes in its session RPCs,
so the two concerns keep one object and separate files.

**Everything a human reads is composed at read time, and that is load-bearing.** The published
record holds the swap's own verdict and nothing else, because the background pass republishes the
bare ``RESIDENCY_SERVING`` constant whenever it finds the cortex back (``residency_regain.py``):
a detail written into the record would survive exactly until the next pass noticed things were
fine. So each fact that can outlive a residency transition keeps its own record and annotates the
report as it is read. There are two, and they are deliberately independent:

- **which peers of the standing residency are missing** (``residency_tiers.py``), a fact about
  now, written by a restart that was refused and healed by a sweep that finds the tier serving;
- **how the last handoff ran** (``residency_pace.py``), a fact about a handoff that has ended,
  written by the deep phase through a port and standing only as long as it still describes now.

Both may be true at once and both are then said, joined by ``residency_state.with_note`` in the
order this module composes them: the standing condition first, the last handoff second. Neither
may annotate a report that is not serving, since mid handoff the seam is already saying what the
swap is doing and a second sentence there would describe one swap twice.
"""

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
    """The honesty surface of ``SwappingModelManager``: what it publishes, and what it answers.

    Reads the four collaborators the manager constructs (`_board`, `_boot`, `_tiers`, `_pace`),
    each declared as a required attribute so any host class must provide them; it holds no state
    of its own, exactly as the seam's servicer mixins do.
    """

    _board: ResidencyBoard
    _boot: BootWatch
    _tiers: StandingTiers
    _pace: HandoffPace

    async def publish_boot_residency(self, *, serving: bool) -> None:
        """Replace the constructor's seed with what boot recovery actually observed.

        Called once by the composition root, before the seam serves, so the first probe of the
        process answers an observation. Deliberately the one writer that touches the report
        **alone** and leaves ``_resident`` where it is: recovery failing to confirm the cortex is
        not the same as knowing it is gone (an unreachable host says nothing about the process it
        supervises, and a load that outran its bound may still finish), so clearing the resident
        would refuse every turn on a machine that may well be serving. The report is display
        only; the lease keeps the forgiving posture boot recovery has always had.

        It is also where the boot watch is seeded, because this is the moment the observation
        being published was made: an answer about the GPU is only ever an answer about the daemon
        that gave it, so recording which daemon that was belongs with recording what it said. A
        later handoff compares against it and reconciles when the answer names a different one.
        """
        await self._boot.seed()
        await self._board.publish_report(RESIDENCY_SERVING if serving else RESIDENCY_BOOT_FAILED)

    @property
    def standing_tiers(self) -> StandingTiers:
        """The peers the standing residency is missing, for boot recovery to write from outside.

        The one belief of this manager's that something other than a swap observes: convergence
        runs before the seam serves and again whenever the daemon is replaced, and both times a
        peer that would not start is a fact about the pool rather than about the cortex. Handing
        the record out keeps the swap back and those two convergences writing one record, which is
        what stops the placer and the seam disagreeing about which tier is down.
        """
        return self._tiers

    @property
    def handoff_pace(self) -> HandoffPace:
        """How the last handoff ran, for the deep phase to write from outside a swap's objects.

        Handed out for the reason above and one more. The phase is built per Converse stream out
        of that stream's own collaborators and holds no residency at all, so the composition root
        gives it this record as a ``PaceSink`` rather than teaching it to reach a manager. One
        record either way: the object the phase writes is the object a probe reads.
        """
        return self._pace

    def residency(self) -> ResidencyReport:
        """What the GPU is serving right now, answered synchronously and without I/O.

        Deliberately not a coroutine and deliberately lock-free, because the seam's ``Health``
        reads it on every probe and the overlay re-probes every few seconds precisely while a
        swap is in flight. Waiting on the lease would hang the indicator for the whole load
        (bounded by ``plan.load_timeout_s``, minutes at tier scale), which is exactly when the
        honest answer is the point; waiting on the residency condition would queue the probe
        behind whatever the scope's end wakes. A plain read is a consistent snapshot: every
        writer publishes the report and the resident together (``residency_board.py``).

        The peers and the last handoff's pace are folded in here rather than into the board, so
        the swap keeps one writer of what the GPU serves: both facts outlive residency
        transitions that would drop them, and the pass that republishes a serving cortex would
        erase either if it were stored. The pace composes outermost, so its sentence lands last.
        """
        return self._pace.note_on(self._tiers.note_on(self._board.report))
