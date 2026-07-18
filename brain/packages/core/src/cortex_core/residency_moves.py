"""The host-facing half of a residency swap: which moves, in which order (ADR-0030 decision 4).

Split out of ``residency.py`` for the line cap, along the seam that module's docstring already
draws: ``SwappingModelManager`` owns *when* the GPU may change hands and who may lease what,
while this owns *what the host is asked to do* once it may. Both halves are pure policy over the
injected ``ModelHost``; neither knows how a model process is actually started, and the readiness
gate arrives as a callable so the manager keeps owning its own bounds.

Two moves, with deliberately opposite failure directions. Swapping in is all or nothing: any
host failure, or a model that will not gate, becomes a ``SwapFailedError`` and the caller's
``finally`` restores. Restoring answers a bool instead, because its caller retries it and only
gives up loudly after that, and because the swap back is the recovery path: it must not raise
its way out of the very thing it is recovering.
"""

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
    """Evict everything, start ``model``, and hold until it is actually serving.

    The order is load bearing and it is the ADR's: the cortex goes first, then every other
    hosted tier (while the deep model is resident it is alone on the GPU), then the new
    resident starts and is gated. ``start`` only *begins* loading, so readiness is observed
    through ``status`` and never inferred from a returned start.
    """
    try:
        await host.stop(plan.cortex_model)
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
    """Put back every tier the swap in evicted, so the standing residency is whole again.

    A swap evicts the cortex AND any other hosted tier, because the deep model is alone on the
    GPU (ADR-0030 decision 8); an exit that restored the cortex alone would leave the subagent
    tier stopped for good while the conductor reopens admission to it, and the next delegated
    run would be placed on a server nothing ever restarted.

    Deliberately after the cortex is serving and gated, and deliberately best effort: the turn
    the user is waiting on needs the cortex, and a tier that will not come back must not be
    reported as the cortex being gone, which is what failing the restore would say.
    """
    for evicted in plan.evict_models:
        try:
            await host.start(evicted)
        except ModelHostError:
            _logger.exception(
                "a tier evicted for the handoff could not be restarted", extra={"model": evicted}
            )
