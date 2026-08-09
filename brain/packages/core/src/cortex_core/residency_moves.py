"""The host-facing half of a residency swap: which moves, in which order (ADR-0030 decision 4)."""

import logging
from collections.abc import Awaitable, Callable

from cortex_core.errors import ModelHostError, SwapFailedError
from cortex_core.model_host import ModelHostState, ResidencyPlan
from cortex_core.ports import ModelHost
from cortex_core.residency_tiers import StandingTiers

# A readiness gate: poll one model until it settles or the plan's bound elapses. Passed in so
# both moves are gated by the same policy their caller uses everywhere else.
type ReadinessGate = Callable[[str], Awaitable[ModelHostState]]

_logger = logging.getLogger(__name__)


async def swap_in(host: ModelHost, plan: ResidencyPlan, model: str, gate: ReadinessGate) -> None:
    """Evict everything, start ``model``, and hold until it is actually serving."""
    try:
        await host.stop(plan.cortex_model)
        if not plan.coresident:
            for evicted in plan.evict_models:
                await host.stop(evicted)
        await _refuse_a_load_the_card_cannot_hold(host, plan, model)
        await host.start(model)
        state = await gate(model)
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
        _logger.error(msg, extra={"model": model, "needed_mib": plan.brain_vram_mib})
        raise SwapFailedError(msg)
    if memory.free_mib < plan.brain_vram_mib:
        msg = (
            f"{model!r} needs {plan.brain_vram_mib} MiB of free device memory and only "
            f"{memory.free_mib} of {memory.total_mib} MiB is free, so it was not started; a "
            "load that does not fit is paged to system memory rather than refused, at roughly "
            "half the decode rate (docs/runbooks/model-swap.md)"
        )
        _logger.error(
            msg,
            extra={
                "model": model,
                "needed_mib": plan.brain_vram_mib,
                "free_mib": memory.free_mib,
                "total_mib": memory.total_mib,
            },
        )
        raise SwapFailedError(msg)
    _logger.info(
        "the card has room for the deep model: model=%s needed_mib=%d free_mib=%d",
        model,
        plan.brain_vram_mib,
        memory.free_mib,
        extra={
            "model": model,
            "needed_mib": plan.brain_vram_mib,
            "free_mib": memory.free_mib,
            "total_mib": memory.total_mib,
        },
    )


async def restore_standing(
    host: ModelHost, plan: ResidencyPlan, model: str, gate: ReadinessGate, tiers: StandingTiers
) -> bool:
    """One attempt at the standing residency: stop ``model``, bring the cortex and its peers up."""
    try:
        await host.stop(model)
        await host.start(plan.cortex_model)
        state = await gate(plan.cortex_model)
    except ModelHostError:
        _logger.exception("the model host failed while restoring the cortex")
        return False
    if state is not ModelHostState.READY:
        return False
    await restart_evicted(host, plan, tiers)
    return True


async def restart_evicted(host: ModelHost, plan: ResidencyPlan, tiers: StandingTiers) -> None:
    """Put back every tier a swap or a crash left evicted, so the standing residency is whole."""
    for evicted in plan.evict_models:
        try:
            await host.start(evicted)
        except ModelHostError:
            _logger.exception(
                "a tier evicted for the handoff could not be restarted", extra={"model": evicted}
            )
            tiers.mark_missing(evicted)
        else:
            tiers.mark_standing(evicted)
