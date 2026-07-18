"""What the GPU is serving right now, in the words the seam shows a human (ADR-0030 d6).

The honesty surface behind ``Health``. ``SwappingModelManager`` publishes one of these values
every time residency changes, and the seam's readiness RPC reads the latest one synchronously,
so the overlay's connection indicator can go amber for the minutes a handoff takes and green
again the moment the usual assistant is back.

All of it is **app-authored**, exactly like the swap's stream notes (``swap_notes.py``): the
model never writes any of it, so a detail cannot be steered by whatever the cortex read before
it escalated. These strings do not ride the escalating turn's stream, which is why they live
here rather than there: a ``StatusUpdate`` is progress on one turn, while a report answers a
probe that any client may make between turns, including one that never saw the handoff start.

Honesty over reassurance, and never a state that cannot be observed: a swap in and a swap back
both leave nothing resident, so the direction is published with the residency rather than
guessed from it, and a restore that gave up says so instead of claiming it is still restoring.
The drain that precedes an eviction is deliberately **serving**: the cortex is still resident
and still answering turns while delegated work quiesces, so the dot stays green until something
is actually unloaded.
"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ResidencyReport:
    """One answer about the GPU: is the usual assistant serving, and if not, what is happening.

    ``serving`` is the whole verdict the seam maps to ``HealthReply.ready``. ``detail`` is
    display-only text for a human deciding whether something is broken (the overlay renders it
    verbatim after "The brain is not serving"), and it is empty while serving, the seam having
    its own thing to say about a healthy brain.
    """

    serving: bool
    detail: str


# The standing residency: the cortex is up and turns run normally. Also what a fresh manager
# reports, matching the boot convergence that runs before the seam serves anything.
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

# The one state no retry cleared: the restore gave up loudly and the GPU serves nothing. It
# stands until the brain restarts and boot recovery converges residency again, which is what
# docs/runbooks/model-swap.md's manual recovery ends with.
RESIDENCY_LOST = ResidencyReport(
    serving=False,
    detail="the usual assistant could not be reloaded after a deep task; recovery is manual",
)
