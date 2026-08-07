"""The host-facing half of a residency swap: which moves, in which order (ADR-0030 decision 4)."""

import logging
from collections.abc import Awaitable, Callable

from cortex_core.errors import ModelHostError, SwapFailedError
from cortex_core.model_host import ModelHostState, ResidencyPlan
from cortex_core.ports import ModelHost

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
        await host.start(model)
        state = await gate(model)
    except ModelHostError as err:
        msg = f"the model host failed while swapping in {model!r}: {err}"
        raise SwapFailedError(msg) from err
    if state is not ModelHostState.READY:
        msg = f"model {model!r} did not become ready in time (last state: {state.value})"
        raise SwapFailedError(msg)


async def restore_standing(
    host: ModelHost, plan: ResidencyPlan, model: str, gate: ReadinessGate
) -> bool:
    """One attempt at the standing residency: stop ``model``, bring the cortex and its peers up.

    ``True`` only when the cortex is genuinely serving again, which is what the caller retries
    on and what the next turn needs.
    """
    try:
        await host.stop(model)
        await host.start(plan.cortex_model)
        state = await gate(plan.cortex_model)
    except ModelHostError:
        _logger.exception("the model host failed while restoring the cortex")
        return False
    if state is not ModelHostState.READY:
        return False
    await _restart_evicted(host, plan)
    return True


async def _restart_evicted(host: ModelHost, plan: ResidencyPlan) -> None:
    """Put back every tier the swap in evicted, so the standing residency is whole again."""
    for evicted in plan.evict_models:
        try:
            await host.start(evicted)
        except ModelHostError:
            _logger.exception(
                "a tier evicted for the handoff could not be restarted", extra={"model": evicted}
            )
