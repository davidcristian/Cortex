"""What the GPU is serving right now, in the words the seam shows a human (ADR-0030 d6).

The reporting surface behind ``Health``. ``SwappingModelManager`` publishes one of these values
every time residency changes, and the seam's readiness RPC reads the latest one synchronously,
so the overlay's connection indicator can go amber for the minutes a handoff takes and green
again the moment the usual assistant is back.

All of it is app-authored, exactly like the swap's stream notes (``swap_notes.py``): the
model never writes any of it, so a detail cannot be steered by whatever the cortex read before
it escalated. These strings do not ride the escalating turn's stream, which is why they live
here rather than there: a ``StatusUpdate`` is progress on one turn, while a report answers a
probe that any client may make between turns, including one that never saw the handoff start.

Every report describes something observed rather than assumed: a swap in and a swap back both
leave nothing resident, so the direction is published with the residency rather than guessed from
it, a restore that stopped retrying says so instead of claiming it is still restoring, and a boot
whose recovery could not settle the cortex says that rather than starting green on an assumption.
The drain that precedes an eviction is deliberately serving: the cortex is still
resident and still answering turns while delegated work quiesces, so the dot stays green until
something is actually unloaded.
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ResidencyReport:
    """One answer about the GPU: is the usual assistant serving, and if not, what is happening.

    ``serving`` is the value the seam maps to ``HealthReply.ready``. ``detail`` is
    display-only text for a human deciding whether something is broken, rendered verbatim by the
    overlay after "The brain is not serving".

    Every constant below leaves it empty while serving, the seam having its own thing to say
    about a healthy brain, but "serving" and "nothing to report" stopped being the same thing
    when the standing residency grew peers that can be down while the cortex is up
    (``residency_tiers.py``). A serving report may therefore carry a detail, which the overlay
    renders after "Brain ready" instead, and the seam prefers it over its own version string.
    """

    serving: bool
    detail: str


def with_note(report: ResidencyReport, note: str) -> ResidencyReport:
    """A serving report that also says ``note``; a report that is not serving, handed back.

    The read-time composition every annotator of a residency report shares, and the reason it is
    one function rather than a rule each of them keeps: a report that is not serving already
    carries the swap's own text, and adding a second sentence to that would be describing one
    handoff twice and calling half of it a fault.

    A second note joins the first rather than replacing it, because the annotators answer
    different questions and have different remedies: which peer of the standing residency is down
    is a fact about now (``residency_tiers.py``), and how the last handoff ran is a fact about a
    handoff that has ended (``residency_pace.py``). Whichever composes outermost is the sentence
    that lands last, so the order of composition is a display decision and never a suppression.
    """
    if not report.serving:
        return report
    joined = f"{report.detail}; {note}" if report.detail else note
    return ResidencyReport(serving=True, detail=joined)


# How the one writer of residency is handed to the pieces that observe a change without owning
# the state: which model the GPU serves (``None`` mid swap) and what to tell a human, published
# together and never one without the other. ``SwappingModelManager._set_resident`` is the only
# implementation; the swap back's retry loop and the boot watch are given it so their findings
# reach the seam without either of them reaching into the manager.
type ResidencyPublisher = Callable[[str | None, ResidencyReport], Awaitable[None]]


# Whether nothing owns the GPU right now: no handoff claimed and no residency scope active. The
# other half of the pair above, and the one the background pass is handed rather than the writer:
# a pass may read the machine at any time and may only write when this answers ``True``.
# Synchronous by contract, which is what makes it usable. Read with nothing awaited between the
# answer and the call it guards, no handoff can begin in the gap, so the callers that must skip a
# pass rather than queue get an answer they can act on instead of a lock they would be waiting on
# the very handoff for. ``SwappingModelManager._fence`` is the only implementation; the
# peer sweep (``residency_sweep.py``) reads it before every start and the board's guarded publish
# (``residency_board.py``) reads it under the condition a claim is taken under.
type Fence = Callable[[], bool]


# The standing residency: the cortex is up and turns run normally. A fresh manager seeds this
# too, and the seed is only ever an assumption, so boot convergence republishes it (or does not)
# from what it actually observed, before the seam serves anything.
RESIDENCY_SERVING = ResidencyReport(serving=True, detail="")

# The swap in, from the moment the lease is taken to the moment the deep model gates ready. It
# covers the eviction as well as the load, because nothing is serving for either.
RESIDENCY_LOADING = ResidencyReport(
    serving=False, detail="swapping to the deep model; this takes a few minutes"
)

# The deep model is resident and answering the handoff. The brain is up and busy, and the usual
# assistant is unloaded, so a turn started now would wait for the swap back.
RESIDENCY_DEEP = ResidencyReport(serving=False, detail="a deep task is in progress")

# The swap back, which is the recovery path: the deep model is stopped and the cortex is loading.
RESIDENCY_RESTORING = ResidencyReport(serving=False, detail="bringing the usual assistant back")

# The one state no retry cleared: the restore stopped retrying and the GPU serves nothing. Nothing
# in the swap will try again, so it stands until something outside one reads the machine: boot
# recovery converging residency after a restart, or the background pass finding the cortex serving
# with the deep tier off the card (``residency_regain.py``), which is why the manual recovery in
# docs/runbooks/model-swap.md no longer ends by restarting the brain.
RESIDENCY_LOST = ResidencyReport(
    serving=False,
    detail="the usual assistant could not be reloaded after a deep task; recovery is manual",
)

# Boot recovery ran and did not leave the cortex serving: the model host was unreachable, or the
# cortex never reported ready inside the load bound. Distinct from the one above because no deep
# task need have happened; this is the state a brain starts in when the GPU is already wrong.
RESIDENCY_BOOT_FAILED = ResidencyReport(
    serving=False,
    detail="the usual assistant did not come up at startup; the model host needs attention",
)
