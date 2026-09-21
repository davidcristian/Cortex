"""One pass over every peer tier of the cortex, not only the ones already recorded down."""

import logging

from cortex_core.errors import ModelHostError, ModelNotHostedError
from cortex_core.model_host import ModelHostState, ResidencyPlan
from cortex_core.ports import ModelHost
from cortex_core.residency_state import Fence
from cortex_core.residency_tiers import BaselineTiers, TierFault

_logger = logging.getLogger(__name__)


async def recheck_tiers(
    host: ModelHost, plan: ResidencyPlan, tiers: BaselineTiers, fence: Fence
) -> None:
    """Ask what every evictable peer is doing, record it, and start the ones that are not."""
    for model in plan.evict_models:
        await _recheck_one(host, model, tiers, fence)


async def _recheck_one(host: ModelHost, model: str, tiers: BaselineTiers, fence: Fence) -> None:
    """Read one tier's state and act on it, or log why the reading could not be taken."""
    # A daemon's roster is read once at its own boot, so this answer cannot change until the
    # daemon is replaced, and a replacement rebuilds the whole record.
    if tiers.fault_of(model) is TierFault.UNHOSTED:
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
    host: ModelHost, model: str, state: ModelHostState, tiers: BaselineTiers, fence: Fence
) -> None:
    """Write what the reading means, and start the tier when the reading says nothing is running."""
    if state is ModelHostState.READY:
        if tiers.fault_of(model) is not None:
            _logger.info(
                "a tier the baseline residency was missing is serving again", extra={"model": model}
            )
        tiers.mark_serving(model)
        return
    if state is ModelHostState.LOADING:
        return
    if tiers.fault_of(model) is None:
        _logger.warning(
            "a tier of the baseline residency stopped without anything asking it to; delegated "
            "work runs on the CPU until it is serving again",
            extra={"model": model, "state": state.value},
        )
    # Before the start, deliberately: the placer must stop sending spawns at that tier
    # whether or not this start happens, and whether or not it succeeds.
    tiers.mark_missing(model)
    if not fence():
        return
    try:
        await host.start(model)
    except ModelHostError as err:
        _unanswered(model, "started", err)


def _unhosted(model: str, tiers: BaselineTiers, err: ModelHostError) -> None:
    """Record a tier this daemon's roster never had, and log it once rather than every pass."""
    _logger.error(
        "the model host does not serve this model at all, so this tier will not be asked about "
        "again until the daemon is replaced: name an artifact for it or drop it from "
        "CORTEX_SWAP_EVICT_MODELS; delegated work runs on the CPU meanwhile",
        extra={"model": model, "error": str(err)},
    )
    tiers.mark_unhosted(model)


# ``verb`` is interpolated into the message rather than attached as a field because
# docs/runbooks/model-swap.md tells an operator to grep for the whole sentence.
def _unanswered(model: str, verb: str, err: ModelHostError) -> None:
    """A host that did not respond leaves the record alone, so a blip cannot close the pool."""
    _logger.warning(
        "a tier of the baseline residency could not be %s",
        verb,
        extra={"model": model, "error": str(err)},
    )
