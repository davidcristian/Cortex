"""One pass over every peer of the standing residency, not only the doubted ones (ADR-0030).

Split from ``residency_tiers.py`` along the seam that already divides this family: that module
owns the record, ``residency_heal.py`` owns when a pass happens, and this owns what a pass does.

**Why it looks at every tier.** The record used to be written only where a ``start`` raised, so it
knew about exactly the tiers a restart had already been refused for. Four conditions escape that
and were measured escaping it against a real supervisor: a peer that accepted its start and then
died, a peer that died quietly between two handoffs, a peer nothing ever started because a
convergence returned before its restart loop, and a boot that could not reach the host at all and
therefore asked nothing to run. In all four the record is empty, the placer goes on believing the
GPU pool is reachable, and every spawn pays a dead load. None of them has a refusal to be written
by, and all four are plain to a ``status``, so the pass asks about every tier a handoff may evict
and writes down what it hears.

**What that costs and what it buys.** One ``status`` per ``evict_models`` tier per interval, where
a pass with an empty record used to ask nothing at all. In the shipped defaults that set is empty
and the pass still asks nothing; in the deployment this exists for it is a couple of loopback calls
a minute. What it buys is a record that is a **cache of the machine** rather than a list of
refusals, which is also what lets it stay in the process: a restart, or a foreign swapper, is
corrected by the next reading instead of being believed for ever.

**The one write to the card, and the fence around it.** Reading is safe at any time; starting a
tier is not, because a handoff may at that moment be deliberately evicting the very tier a pass
wants back. So the fence is a callable the manager owns (no handoff claimed, no residency scope
active), it is read at the top of the pass, and it is read **again immediately before every
start**, synchronously, with nothing awaited in between so no handoff can begin in the gap. A
start already in flight when a handoff begins is left to the supervisor's own per-model lock: the
swap in stops these very tiers first and does not return until each child is reaped.
"""

import logging
from collections.abc import Callable

from cortex_core.errors import ModelHostError, ModelNotHostedError
from cortex_core.model_host import ModelHostState, ResidencyPlan
from cortex_core.ports import ModelHost
from cortex_core.residency_tiers import StandingTiers, TierFault

# Whether a pass may still write to the card: no handoff claimed and no residency scope active.
# Synchronous by contract, because the whole worth of asking again just before a start is that
# nothing else can run between the answer and the call.
type Fence = Callable[[], bool]

_logger = logging.getLogger(__name__)


async def sweep_tiers(
    host: ModelHost, plan: ResidencyPlan, tiers: StandingTiers, fence: Fence
) -> None:
    """Ask what every evictable peer is doing, record it, and start the ones that are not.

    Never raises: a tier the host cannot answer about must not stop the others being swept, which
    is the same rule the pass this replaces kept for the same reason.
    """
    for model in plan.evict_models:
        await _sweep_one(host, model, tiers, fence)


async def _sweep_one(host: ModelHost, model: str, tiers: StandingTiers, fence: Fence) -> None:
    """Read one tier's state and act on it, or say why the reading could not be taken."""
    if tiers.fault_of(model) is TierFault.UNHOSTED:
        # The answer is this daemon's env, read once at its own boot, so no pass will ever get a
        # different one. A replacement daemon rebuilds the whole record (``residency_watch.py``).
        return
    try:
        state = await host.status(model)
    except ModelNotHostedError as err:
        _unhosted(model, tiers, err)
        return
    except ModelHostError as err:
        _unanswered(model, "asked about", err)
        return
    await _act_on(host, model, state, tiers, fence)


async def _act_on(
    host: ModelHost, model: str, state: ModelHostState, tiers: StandingTiers, fence: Fence
) -> None:
    """Write what the reading means, and start the tier when the reading says nothing is running.

    ``LOADING`` is the one state that means neither: it is on its way, so starting it again would
    be a no-op at the supervisor and marking it would close the GPU on a tier that is about to
    serve. A tier already believed missing stays believed missing through its whole load.
    """
    if state is ModelHostState.READY:
        if tiers.fault_of(model) is not None:
            _logger.info(
                "a tier the standing residency was missing is serving again", extra={"model": model}
            )
        tiers.mark_standing(model)
        return
    if state is ModelHostState.LOADING:
        return
    if tiers.fault_of(model) is None:
        _logger.warning(
            "a tier of the standing residency stopped without anything asking it to: model=%s "
            "state=%s; delegated work runs on the CPU until it is serving again",
            model,
            state.value,
            extra={"model": model, "state": state.value},
        )
    # Before the start, deliberately: the placer must stop sending spawns at that tier whether or
    # not this start is fenced out, and whether or not it succeeds.
    tiers.mark_missing(model)
    if not fence():
        return
    try:
        await host.start(model)
    except ModelHostError as err:
        # Deliberately one arm where the reading above has two. A 404 here, after a ``status`` the
        # same daemon answered, is a daemon replaced between two calls of one pass, and the next
        # pass's reading settles which it is; there is nothing to record from it that a fresh
        # reading would not immediately overwrite.
        _unanswered(model, "started", err)


def _unhosted(model: str, tiers: StandingTiers, err: ModelHostError) -> None:
    """Record a tier this daemon's roster never had, and say so once rather than every pass.

    Said once because the pass never comes back: a tier with this fault is skipped at the top of
    every later pass, so this line is written where the belief changes and nowhere else.
    """
    _logger.error(
        "the model host does not serve %r at all, so this tier will not be asked about again "
        "until the daemon is replaced: name an artifact for it or drop it from "
        "CORTEX_SWAP_EVICT_MODELS; delegated work runs on the CPU meanwhile: %s",
        model,
        err,
        extra={"model": model, "error": str(err)},
    )
    tiers.mark_unhosted(model)


def _unanswered(model: str, verb: str, err: ModelHostError) -> None:
    """A host that could not answer leaves the record alone, so a blip cannot close the pool."""
    _logger.warning(
        "a tier of the standing residency could not be %s: model=%s error=%s",
        verb,
        model,
        err,
        extra={"model": model, "error": str(err)},
    )
