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

    A ``coresident`` plan skips the second step and only the second step: the cortex still goes,
    because no measured pairing of it and a deep candidate fits 24 GB, while the standing peers
    the deployment has measured as fitting stay exactly where they are.

    Between the evictions and the start sits the fit check, at the one moment it can mean
    anything: everything this handoff intends to unload is gone, nothing has been allocated yet,
    and what the card reports free is exactly the room the deep model is about to ask for.
    """
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
    """Fail the swap before the load when the free device memory is short of the plan's figure.

    Off unless the deployment declared ``brain_vram_mib``, which is what a co-resident deployment
    is required to do: with no figure there is nothing to compare against and this returns at
    once, so a stack that never declared one behaves exactly as it did.

    **What this can detect, stated narrowly on purpose.** It compares one number the deployment
    measured against one number the card reports, at the instant before the allocation. That is
    the only instant at which free memory is evidence: measured 2026-08-07 on a 24 GB card, a
    genuine fit and a 4676 MiB overcommit both read about 23.6 GB used and about 0.5 GB free
    **afterwards**, because the driver pages the excess to system memory and reports success, so a
    check that looked at the card once both tiers were up would license exactly the configuration
    it exists to refuse. It therefore detects a card that has too little room left, and nothing
    else: not a declared figure that is wrong (a deployment that under-declares gets no
    protection, which is why the runbook says to measure decode and not memory), not memory some
    other process on the card takes during the minutes the load runs, and not a spill once it has
    happened. Its answer is "there was not room", never "it fitted".

    ``None`` from the host means it cannot see a card at all, which fails closed: a deployment
    that asked for a fit check and cannot have one is refused rather than run unchecked.
    """
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

    Deliberately unconditional too, ``coresident`` included, where the swap in is not: a start
    against a tier the swap never stopped is a no-op the supervisor answers from its own child
    table, and if that tier died of its own accord while the deep model held the card, this is
    the one place that notices and brings it back.
    """
    for evicted in plan.evict_models:
        try:
            await host.start(evicted)
        except ModelHostError:
            _logger.exception(
                "a tier evicted for the handoff could not be restarted", extra={"model": evicted}
            )
