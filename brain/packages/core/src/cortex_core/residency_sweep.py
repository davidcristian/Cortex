"""One pass over every peer of the standing residency, not only the doubted ones (ADR-0030)."""

import logging

from cortex_core.errors import ModelHostError, ModelNotHostedError
from cortex_core.model_host import ModelHostState, ResidencyPlan
from cortex_core.ports import ModelHost
from cortex_core.residency_state import Fence
from cortex_core.residency_tiers import StandingTiers, TierFault

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
    """Write what the reading means, and start the tier when the reading says nothing is running."""
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
