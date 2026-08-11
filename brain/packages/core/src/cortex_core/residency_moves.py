"""The host-facing half of a residency swap: which moves, in which order (ADR-0030 decision 4)."""

import logging
from collections.abc import Awaitable, Callable

from cortex_core.errors import ModelHostError, ModelNotHostedError, SwapFailedError
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
        await _stop_what_was_swapped_in(host, model)
        await host.start(plan.cortex_model)
        state = await gate(plan.cortex_model)
    except ModelHostError:
        _logger.exception("the model host failed while restoring the cortex")
        return False
    if state is not ModelHostState.READY:
        return False
    await restart_evicted(host, plan, tiers)
    return True


async def _stop_what_was_swapped_in(host: ModelHost, model: str) -> None:
    """Take the scope's own resident off the card, unless this host never had such a tier.

    Every other failure propagates to the caller's ``except``, because a model that is resident
    and will not stop is exactly the state the retry exists for.
    """
    try:
        await host.stop(model)
    except ModelNotHostedError as err:
        _logger.warning(
            "the model host does not serve %r, so there was nothing of it to stop: %s",
            model,
            err,
            extra={"model": model, "error": str(err)},
        )


async def restart_evicted(host: ModelHost, plan: ResidencyPlan, tiers: StandingTiers) -> None:
    """Put back every tier a swap or a crash left evicted, so the standing residency is whole."""
    for evicted in plan.evict_models:
        try:
            await host.start(evicted)
        except ModelNotHostedError:
            # A different fault from a host that would not: the id is not in this daemon's roster,
            # which is env it read once at its own boot, so the retry pass stops asking about it
            # rather than spending a control call an interval on a fixed answer.
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
            tiers.mark_standing(evicted)
