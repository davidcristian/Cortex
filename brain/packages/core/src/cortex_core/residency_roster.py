"""Compares the evict list with the models the model host reports it has."""

import logging

from cortex_core.errors import ModelHostError
from cortex_core.model_host import ResidencyPlan
from cortex_core.ports import ModelHost

_logger = logging.getLogger(__name__)

_UNLISTED = "the model host has a model the evict list leaves out, so a handoff does not stop it"
_UNASKED = "the model host could not be asked which models it has, so the evict list is unchecked"


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
