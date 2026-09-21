"""Recovering the usual residency without a turn: read the machine, publish when it agrees."""

import logging

from cortex_core.errors import ModelHostError, ModelNotHostedError
from cortex_core.model_host import ModelHostState, ResidencyPlan
from cortex_core.ports import ModelHost
from cortex_core.residency_board import ResidencyBoard
from cortex_core.residency_charge import charge_baseline
from cortex_core.residency_pass import recheck_tiers
from cortex_core.residency_state import RESIDENCY_SERVING, Fence
from cortex_core.residency_tiers import BaselineTiers

_logger = logging.getLogger(__name__)


async def recheck_baseline_residency(
    host: ModelHost, plan: ResidencyPlan, board: ResidencyBoard, tiers: BaselineTiers, fence: Fence
) -> None:
    """One pass over the usual residency: every evictable peer, and then the resident."""
    await recheck_tiers(host, plan, tiers, fence)
    await regain_residency(host, plan, board, tiers, fence)


async def regain_residency(
    host: ModelHost, plan: ResidencyPlan, board: ResidencyBoard, tiers: BaselineTiers, fence: Fence
) -> None:
    """Publish the cortex as the resident again when the machine says it is, or do nothing."""
    if board.report.serving:
        return
    if not await _cortex_is_serving(host, plan.cortex_model):
        return
    if not await _deep_tier_is_off_the_card(host, plan.brain_model):
        return
    if await board.publish_between_handoffs(plan.cortex_model, RESIDENCY_SERVING, fence):
        charge_baseline(tiers.placer)
        _logger.info(
            "the cortex is serving again, so residency was regained without a restart",
            extra={"model": plan.cortex_model},
        )


async def _cortex_is_serving(host: ModelHost, model: str) -> bool:
    """Whether the cortex is actually ready right now."""
    try:
        return await host.status(model) is ModelHostState.READY
    except ModelHostError as err:
        _logger.debug(
            "the model host could not be asked whether the cortex is serving again",
            extra={"model": model, "error": str(err)},
        )
        return False


async def _deep_tier_is_off_the_card(host: ModelHost, model: str) -> bool:
    """Whether the deep model is off the GPU, so a serving cortex is the usual state."""
    try:
        state = await host.status(model)
    except ModelNotHostedError:
        return True
    except ModelHostError as err:
        _logger.debug(
            "the model host could not be asked whether the deep model is still resident",
            extra={"model": model, "error": str(err)},
        )
        return False
    return state not in (ModelHostState.READY, ModelHostState.LOADING)
