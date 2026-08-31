"""How the last handoff ran, for as long as that is still a fact about now (ADR-0030).

The deep phase watches decode cadence because a handoff that overcommits the card still succeeds:
both tiers report ``ready``, the fit check has already passed on a figure that was too low or on
room the desktop took during the load, and free memory afterwards reads like a genuine fit. Only
throughput differs. Until this module the whole consequence of that watch was one ``warning``
record, so a spill looked exactly like a fit to everyone who was not tailing the container, which
is exactly the deployment the automatic co-residency latch was declined in favour of.

So the result is carried on the same surface a missing peer already uses: a serving residency
report gains a detail, ``Health`` prefers that detail over its version string, and the overlay
renders it after "Brain ready" with no overlay change at all. It is composed at read time, in
``residency()``, and never written into the published record, because the background pass
republishes the bare ``RESIDENCY_SERVING`` constant whenever it finds the cortex back
(``residency_regain.py``) and would erase anything written there.

The standing rule is the design question here. A spill is a fact about one handoff and the record
it is carried on is a fact about now, so a note that never cleared would be a second way to be
wrong about the card. Two things end it, and they answer the two ways a spill ends:

- A later handoff decides it, in both directions. A handoff that held its pace clears the note
  on the spot, because a tier that reached its floor is the only direct evidence there is that the
  card has room again; one that spilled again re-arms it from that moment. A handoff that settled
  no reading changes nothing, since a completion too short to judge is not a pass, and the
  phase never calls the port at all in that case.
- Otherwise it lapses on its own, after ``DEFAULT_SPILL_DWELL_S``. Escalation is rare on a
  personal machine, so waiting for the next handoff can mean waiting days, and the note must not
  outlive the machine state it describes. An hour is chosen from the two lifetimes a spill really
  has: memory the desktop took is gone the moment that window is closed, while a declared cost
  that is too low is env and outlives everything until the brain restarts, which takes the note
  with it. An hour is long enough to still be there when somebody who walked away from a
  minutes-long deep task comes back and looks, and short enough that a card left alone for an
  afternoon is not still being described by a reading from the morning.

The dwell is a constructor bound rather than env, and deliberately: it decides how long one
sentence is displayed and nothing about what the machine does, so it is the kind of number a
deployment may want to tune later and no deployment should have to set now.

Both notes can be true at once, and both are shown. A peer that is down and a handoff that
spilled have different remedies (put the tier back; give the card room), so suppressing either
would send an operator to fix one thing while the other stayed broken. They join through
``residency_state.with_note``, standing condition first and last handoff second, which is the
order of ``residency()``'s own composition.
"""

from datetime import datetime, timedelta

from cortex_core.ports import Clock
from cortex_core.residency_state import ResidencyReport, with_note

# How long a spill note stands when no later handoff decides it. One hour, argued above: past it
# the note stops describing now, so there is nothing left to say.
DEFAULT_SPILL_DWELL_S = 3600.0

# What ``Health`` says while the last handoff is recorded as having spilled. It is added only to a
# serving report, so the overlay renders it after "Brain ready": turns work and delegation works,
# and what
# changed is that the one thing this brain does slowly did it far more slowly than it should. It
# names the deployment's own measurement rather than a rate, because the reader of a tooltip has
# no way to judge a number, and it names the consequence rather than the mechanism for the same
# reason: "overcommitted", "paged", and "decode rate" are all true and none of them tells a person
# what they are losing. What they are losing is time on every deep task until the card has room.
SPILLED_PACE_DETAIL = (
    "the last deep task ran far slower than this deployment measured for it, so deep tasks are "
    "taking much longer than they should"
)


class HandoffPace:
    """Whether the last handoff held its pace, and how long that answer still describes now.

    Held by ``SwappingModelManager`` beside the peer record it composes with, written by the deep
    phase through the ``PaceSink`` port (the phase holds no residency and must not reach for the
    manager), and read by the seam through ``residency()``.

    Every method is synchronous and awaits nothing, which is what makes it safe without a lock:
    a coroutine's read-modify-write here runs to completion without interleaving, exactly as the
    peer record's does. It is deliberately not stored anywhere (the one hard rule): what is
    kept is one timestamp about the process's own last handoff, and a process that restarts has
    no last handoff to describe.
    """

    def __init__(self, clock: Clock, *, dwell_s: float = DEFAULT_SPILL_DWELL_S) -> None:
        if dwell_s <= 0:
            msg = f"HandoffPace dwell_s must be > 0, got {dwell_s}"
            raise ValueError(msg)
        self._clock = clock
        self._dwell = timedelta(seconds=dwell_s)
        self._spilled_at: datetime | None = None

    def note_pace(self, *, spilled: bool) -> None:
        """Record how the handoff that just ended ran: the ``PaceSink`` port, implemented.

        A spill stamps the moment it was observed, so the dwell runs from the handoff rather than
        from whenever a probe next arrives, and a second spill re-arms it. Holding the pace clears
        the note outright, which is the one direct piece of evidence that the card has room again:
        the tier reached the rate this deployment measured for it, on this deployment's own card.

        Never called at all when the phase settled no reading, so "nothing was judged" cannot
        clear a note the way "it was fine" does.
        """
        self._spilled_at = self._clock.now() if spilled else None

    def note_on(self, report: ResidencyReport) -> ResidencyReport:
        """The report a probe should see: unchanged, or a serving one that says the card is tight.

        Composed outermost in ``residency()``, so a peer that is down is named first and this is
        the sentence that lands last. A report that is not serving is handed straight back by
        ``with_note``: mid handoff the seam is already saying what the swap is doing, and the
        reading from the previous handoff would be read as one about that one.

        A lapsed note is answered rather than erased. A probe is a read, and this is the object
        every probe reads: clearing here would make the seam's one lock-free path a writer, and
        the answer is identical either way.
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
