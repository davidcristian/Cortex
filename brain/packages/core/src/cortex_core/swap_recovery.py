"""Boot recovery: what a restart owes a handoff that a crash interrupted."""

import logging

from cortex_core.errors import HandoffStoreError, ModelHostError, ModelNotHostedError
from cortex_core.handoff import HandoffState
from cortex_core.model_host import ModelHostState, ResidencyPlan
from cortex_core.model_ready import await_model_ready
from cortex_core.ports import Clock, HandoffStore, ModelHost, Sleeper
from cortex_core.residency_moves import restart_evicted
from cortex_core.residency_tiers import BaselineTiers
from cortex_core.swap_reasons import STRANDED_REASON

_logger = logging.getLogger(__name__)


async def recover_handoffs(
    handoffs: HandoffStore,
    host: ModelHost,
    plan: ResidencyPlan,
    tiers: BaselineTiers,
    *,
    clock: Clock,
    sleeper: Sleeper,
) -> bool:
    """Fail a crash-stranded handoff, converge the GPU, and answer whether the cortex serves."""
    await _fail_stranded_handoff(handoffs)
    return await converge_residency(host, plan, tiers, clock=clock, sleeper=sleeper)


async def _fail_stranded_handoff(handoffs: HandoffStore) -> None:
    """Mark the one non-terminal record ``FAILED``, saying so on the record as well as here."""
    try:
        record = await handoffs.active()
        if record is None:
            return
        _logger.warning(
            "a handoff did not survive the restart; marking it failed",
            extra={
                "session_id": record.session_id,
                "turn_id": record.handoff_id,
                "state": record.state.value,
            },
        )
        await handoffs.transition(record.handoff_id, HandoffState.FAILED, failure=STRANDED_REASON)
    except HandoffStoreError:
        _logger.exception("could not read or fail a stranded handoff at startup")


async def converge_residency(
    host: ModelHost, plan: ResidencyPlan, tiers: BaselineTiers, *, clock: Clock, sleeper: Sleeper
) -> bool:
    """Clear the GPU, settle the cortex on it, put the usual residency back, and report."""
    # The tiers a swap evicts are stopped first and restarted last, because a crash can leave
    # one holding the VRAM the cortex needs before the cortex itself can load.
    for peer in plan.evict_models:
        await _clear_peer(host, peer)
    try:
        await _clear_deep(host, plan.brain_model)
    except ModelHostError:
        _logger.exception(
            "the model host failed while clearing the deep model at boot",
            extra={"model": plan.brain_model},
        )
        return False
    try:
        settled = await _settle_cortex(host, plan, clock=clock, sleeper=sleeper)
    except ModelNotHostedError:
        _logger.exception(
            "the model host does not serve the cortex this brain names, so nothing can",
            extra={"model": plan.cortex_model},
        )
        return False
    except ModelHostError:
        _logger.exception(
            "the model host was unreachable during boot recovery",
            extra={"model": plan.cortex_model},
        )
        return False
    await restart_evicted(host, plan, tiers)
    return settled


async def _clear_deep(host: ModelHost, model: str) -> None:
    """Take the deep model off the card, or say why this host has no such tier to take off."""
    try:
        if await host.status(model) is not ModelHostState.STOPPED:
            _logger.warning(
                "stopping a model left running by an interrupted handoff", extra={"model": model}
            )
            await host.stop(model)
    except ModelNotHostedError as err:
        _logger.error(  # noqa: TRY400 -- the fault is the deployment's config, not this stack
            "escalation is enabled but the model host does not serve the deep model, so no "
            "handoff can ever run: name an artifact for that tier (CORTEX_MODEL_FILE_BRAIN) or "
            "turn escalation off (CORTEX_ESCALATION); the cortex is unaffected",
            extra={"model": model, "error": str(err)},
        )


async def _clear_peer(host: ModelHost, model: str) -> None:
    """Take one evictable peer off the card before the cortex loads, or say why it could not."""
    try:
        if await host.status(model) is not ModelHostState.STOPPED:
            _logger.warning(
                "stopping a model left running by an interrupted handoff", extra={"model": model}
            )
            await host.stop(model)
    except ModelHostError:
        _logger.exception(
            "a tier the baseline residency includes could not be cleared at boot",
            extra={"model": model},
        )


async def _settle_cortex(
    host: ModelHost, plan: ResidencyPlan, *, clock: Clock, sleeper: Sleeper
) -> bool:
    """Make sure the cortex is serving, log an error when it is not, and return which."""
    if await host.status(plan.cortex_model) is ModelHostState.READY:
        return True
    await host.start(plan.cortex_model)
    state = await await_model_ready(
        host, plan.cortex_model, clock=clock, sleeper=sleeper, plan=plan
    )
    if state is not ModelHostState.READY:
        _logger.error(
            "the cortex is not serving after boot recovery; turns will fail until it is",
            extra={"model": plan.cortex_model, "state": state.value},
        )
        return False
    return True
