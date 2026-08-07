"""The two edges of the handoff window, as the subagent placer sees them (ADR-0030).

``residency_moves.py`` owns what the host is asked to do during a swap; this owns what the
*accounting* is asked to believe while it happens. Both are pure policy the residency scope
calls, and this one is deliberately tiny: a placer is told which model holds the card, and
nothing here decides anything else.

**Why the placer has to be told at all.** ``VramBudgetPlacer`` fit-tests every GPU-placed spawn
against ``soft_cap - resident - placed``, and outside a handoff the resident is the cortex, which
is true. Inside one it is false twice over: the cortex has been evicted, so its reservation
credits room to nobody, and the deep model that took the card (19117 to 19125 MiB measured on a
24 GB card, ADR-0030 co-residency addendum) is charged nowhere at all, because it is not placed
through the placer. The window was unreachable while every handoff drained the subagent pool
first, since no spawn could be placed inside it; ``CORTEX_SWAP_CORESIDENT`` is exactly the
deployment that skips the drain so delegated work keeps flowing, which is what made this
reachable and what makes it worth fixing rather than recording.

**What is charged, and why it is a declared figure rather than a reading.** The plan's
``brain_vram_mib`` is the deployment's own measurement of its deep tier, and it is not taken on
trust: ``swap_in``'s fit check compares that same number against what the card reports free
immediately before the load, and refuses the handoff when the card is short. So by the time the
window matters, a real reading has cleared the declared figure at the one instant such a reading
is evidence. Reading the card here instead would put an HTTP call to the sidecar inside
``place``, which is synchronous and lock-free by design (no ``await``, so a batch of concurrent
spawns races the ledger correctly); making it async to fetch a number that the swap has already
checked would buy accuracy the spawn path cannot spend.

**Ordering, since the fit check and this now reason about the same card.** The charge is written
*before* ``swap_in`` runs, so it is in force while the check reads the card and while the weights
load. That direction is the safe one and it closes a gap the check cannot see on its own: a spawn
admitted in the seconds between the reading and the allocation would consume exactly the room the
check just measured. The reversal waits for the other end: it is written only once the cortex is
genuinely serving again, so a restore that gave up loudly leaves the handoff charge standing and
keeps spawning on the CPU, rather than admitting GPU work onto a card whose state nobody knows.

**Off unless the deployment declared a figure.** With ``brain_vram_mib`` zero (the shipped
default) there is no honest number to charge, and charging nothing would be worse than today: it
would credit the evicted cortex's reservation back while the deep model holds the card. So that
deployment keeps exactly the arithmetic it has always had.
"""

from cortex_core.model_host import ResidencyPlan
from cortex_core.ports import SubagentPlacer


def charge_handoff(placer: SubagentPlacer | None, plan: ResidencyPlan) -> None:
    """Tell the placer the deep model holds the card, when the deployment said what it costs."""
    if placer is not None and plan.brain_vram_mib > 0:
        placer.charge_handoff(resident_gb=plan.brain_vram_gb)


def charge_standing(placer: SubagentPlacer | None) -> None:
    """Tell the placer the cortex holds the card again (idempotent, and a no-op with no placer)."""
    if placer is not None:
        placer.charge_standing()
