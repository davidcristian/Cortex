"""The host-facing half of a residency swap: what the host is asked, in which order."""

import logging
from collections.abc import Awaitable, Callable

from cortex_core.errors import ModelHostError, ModelNotHostedError, SwapFailedError
from cortex_core.model_host import ModelHostState, ResidencyPlan
from cortex_core.ports import ModelHost
from cortex_core.residency_tiers import BaselineTiers

type ReadinessCheck = Callable[[str], Awaitable[ModelHostState]]

_logger = logging.getLogger(__name__)

_NO_DEVICE_MEMORY = (
    "the model host reports no device memory, so the fit check has nothing to compare against"
)
_CARD_TOO_SHORT = "the card has too little free memory for the deep model, so it was not started"


async def is_unhosted(host: ModelHost, model: str) -> bool:
    """Whether this host says it has no such logical model at all."""
    try:
        await host.status(model)
    except ModelNotHostedError:
        return True
    except ModelHostError as err:
        _logger.warning(
            "the model host could not be asked whether it serves this model, so the handoff was "
            "not refused on that ground",
            extra={"model": model, "error": str(err)},
        )
    return False


async def swap_in(
    host: ModelHost, plan: ResidencyPlan, model: str, check_ready: ReadinessCheck
) -> None:
    """Evict everything, start ``model``, and hold until it is actually serving."""
    try:
        await host.stop(plan.cortex_model)
        if not plan.coresident:
            for evicted in plan.evict_models:
                await host.stop(evicted)
        await _refuse_a_load_the_card_cannot_hold(host, plan, model)
        await host.start(model)
        state = await check_ready(model)
    except ModelNotHostedError as err:
        msg = (
            f"the model host does not serve {model!r} at all, so this deployment cannot escalate "
            f"until that tier is in its roster (docs/runbooks/model-swap.md): {err}"
        )
        raise SwapFailedError(msg) from err
    except ModelHostError as err:
        msg = f"the model host failed while swapping in {model!r}: {err}"
        raise SwapFailedError(msg) from err
    if state is not ModelHostState.READY:
        msg = f"model {model!r} did not become ready in time (last state: {state.value})"
        raise SwapFailedError(msg)


async def _refuse_a_load_the_card_cannot_hold(
    host: ModelHost, plan: ResidencyPlan, model: str
) -> None:
    """Fail the swap before the load when the free device memory is short of the plan's figure."""
    if plan.brain_vram_mib <= 0:
        return
    memory = await host.device_memory()
    if memory is None:
        msg = (
            f"the model host reports no device memory, so there is no way to tell whether "
            f"{model!r} fits in the {plan.brain_vram_mib} MiB it was declared to need; the "
            "handoff is refused rather than run unchecked"
        )
        _logger.error(_NO_DEVICE_MEMORY, extra={"model": model, "needed_mib": plan.brain_vram_mib})
        raise SwapFailedError(msg)
    if memory.free_mib < plan.brain_vram_mib:
        msg = (
            f"{model!r} needs {plan.brain_vram_mib} MiB of free device memory and only "
            f"{memory.free_mib} of {memory.total_mib} MiB is free, so it was not started; a "
            "load that does not fit is paged to system memory rather than refused, at roughly "
            "half the decode rate (docs/runbooks/model-swap.md)"
        )
        _logger.error(
            _CARD_TOO_SHORT,
            extra={
                "model": model,
                "needed_mib": plan.brain_vram_mib,
                "free_mib": memory.free_mib,
                "total_mib": memory.total_mib,
            },
        )
        raise SwapFailedError(msg)
    _logger.info(
        "the card has room for the deep model",
        extra={
            "model": model,
            "needed_mib": plan.brain_vram_mib,
            "free_mib": memory.free_mib,
            "total_mib": memory.total_mib,
        },
    )


async def restore_baseline(
    host: ModelHost,
    plan: ResidencyPlan,
    model: str,
    check_ready: ReadinessCheck,
    tiers: BaselineTiers,
) -> str | None:
    """One attempt to restore the usual set: stop ``model``, start the cortex and its peers."""
    try:
        await _stop_what_was_swapped_in(host, model)
    except ModelHostError:
        _logger.exception(
            "the model host failed while taking the swapped-in model off the card",
            extra={"model": model},
        )
        return model
    try:
        await host.start(plan.cortex_model)
        state = await check_ready(plan.cortex_model)
    except ModelHostError:
        _logger.exception(
            "the model host failed while restoring the cortex", extra={"model": plan.cortex_model}
        )
        return plan.cortex_model
    if state is not ModelHostState.READY:
        return plan.cortex_model
    await restart_evicted(host, plan, tiers)
    return None


async def _stop_what_was_swapped_in(host: ModelHost, model: str) -> None:
    """Take the scope's own resident off the card, unless this host never had such a tier."""
    try:
        await host.stop(model)
    except ModelNotHostedError as err:
        _logger.warning(
            "the model host does not serve this model, so there was nothing of it to stop",
            extra={"model": model, "error": str(err)},
        )


async def restart_evicted(host: ModelHost, plan: ResidencyPlan, tiers: BaselineTiers) -> None:
    """Put back every tier a swap or a crash left evicted, so the usual set is complete."""
    for evicted in plan.evict_models:
        try:
            await host.start(evicted)
        except ModelNotHostedError:
            # A different fault from a host that failed to start it: the id is not in this
            # daemon's roster, which it read once at its own boot, so the retry pass stops
            # asking about it instead of spending a control call every interval.
            _logger.exception(
                "a tier named for eviction is not in the model host's roster at all",
                extra={"model": evicted},
            )
            tiers.mark_unhosted(evicted)
        except ModelHostError:
            _logger.exception(
                "a tier evicted for the handoff could not be restarted", extra={"model": evicted}
            )
            tiers.mark_missing(evicted)
        else:
            tiers.mark_serving(evicted)
