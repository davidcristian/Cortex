"""What boot recovery asks the model host about the tiers a handoff stops and starts."""

import logging

from cortex_core.errors import ModelHostError, ModelNotHostedError
from cortex_core.model_host import ResidencyPlan
from cortex_core.ports import ModelHost

_logger = logging.getLogger(__name__)

_UNLISTED = "the model host has a model the evict list leaves out, so a handoff does not stop it"
_UNASKED = "the model host could not be asked which models it has, so the evict list is unchecked"
_UNSTARTABLE = "the model host cannot start the deep model, so every handoff fails until it can"
_GAP_UNASKED = "the model host could not be asked whether it can start the deep model"


async def warn_of_unlisted_models(host: ModelHost, plan: ResidencyPlan) -> tuple[str, ...]:
    """Log a warning for each hosted model a handoff would leave loaded, and return those ids."""
    if plan.coresident:
        return ()
    try:
        roster = await host.roster()
    except ModelHostError as err:
        _logger.warning(_UNASKED, extra={"error": str(err)})
        return ()
    stopped = (plan.cortex_model, plan.brain_model, *plan.evict_models)
    unlisted = tuple(model for model in roster or () if model not in stopped)
    for model in unlisted:
        _logger.warning(
            _UNLISTED,
            extra={"model": model, "setting": "CORTEX_SWAP_EVICT_MODELS"},
        )
    return unlisted


async def warn_of_an_unstartable_deep_model(host: ModelHost, plan: ResidencyPlan) -> str | None:
    """Log the reason the host names for not starting the deep model, and return it."""
    try:
        gap = await host.start_gap(plan.brain_model)
    except ModelNotHostedError:
        # Boot recovery has already logged a deep tier the host does not serve at all.
        return None
    except ModelHostError as err:
        _logger.warning(_GAP_UNASKED, extra={"model": plan.brain_model, "error": str(err)})
        return None
    if gap is not None:
        _logger.warning(_UNSTARTABLE, extra={"model": plan.brain_model, "reason": gap})
    return gap
