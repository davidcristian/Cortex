"""The host-facing half of a residency swap: what the host is asked, in which order (ADR-0030 d4).

Split out of ``residency.py`` for the line cap, along the seam that module's docstring already
draws: ``SwappingModelManager`` owns *when* the GPU may change hands and who may lease what,
while this owns *what the host is asked* once it may. Both halves are pure policy over the
injected ``ModelHost``; neither knows how a model process is actually started, and the readiness
gate arrives as a callable so the manager keeps owning its own bounds.

Two moves, with deliberately opposite failure directions, and above them the one question a
caller asks before committing to either. Swapping in is all or nothing: any host failure, or a
model that will not gate, becomes a ``SwapFailedError`` and the caller's ``finally`` restores.
Restoring answers the model it failed on instead, because its caller retries it and only gives up
loudly after that, and because the swap back is the recovery path: it must not raise its way out
of the very thing it is recovering. The question (``is_unhosted``) answers a bool for a reason of
its own: a swap that cannot possibly work should be refused before it starts rather than discovered
halfway through itself, with the cortex already unloaded and minutes owed to putting it back.

The last step of the second move, ``restart_evicted``, is public because boot recovery ends the
same way (``swap_recovery.py``): putting the standing residency's peers back is one move written
once, so the two paths cannot drift into disagreeing about what a refused start means.
"""

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


async def is_unhosted(host: ModelHost, model: str) -> bool:
    """Whether this host says it carries no such logical model at all.

    The question a handoff asks before it spends anything, and it is asked rather than remembered
    because of who owns the answer: a roster is env one supervisor process read at its own boot,
    so the verdict is about the daemon answering right now and about no other. Re-deriving it
    costs one ``status`` on a tier that is stopped, which is less than the machinery any cache of
    it would need to stay safe across the restart that changes it.

    ``True`` only for the host's own narrow refusal. Every other failure means the question went
    unanswered, and an unanswered question must not read as a refusal: over-refusing here would
    turn one unreachable moment into "this deployment cannot escalate", while a swap that goes
    ahead against a host that is really down fails at its very next move and reports the failure
    that really happened.
    """
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

    A model the host does not carry fails the same way and says something different, because the
    two failures ask for different repairs: a host that broke is retried by the next handoff, while
    a tier no roster has will refuse every handoff this deployment ever attempts, and the note the
    user is owed should not describe that as the machine having failed.
    """
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
        "the card has room for the deep model",
        extra={
            "model": model,
            "needed_mib": plan.brain_vram_mib,
            "free_mib": memory.free_mib,
            "total_mib": memory.total_mib,
        },
    )


async def restore_standing(
    host: ModelHost, plan: ResidencyPlan, model: str, gate: ReadinessGate, tiers: StandingTiers
) -> str | None:
    """One attempt at the standing residency: stop ``model``, bring the cortex and its peers up.

    ``None`` only when the cortex is genuinely serving again, which is what the caller retries
    on and what the next turn needs; anything else is the id of the model this attempt failed
    on. The sense is therefore inverted from the bool it used to be, and deliberately so: the
    answer now reads as *what refused* rather than as *did it work*, and there is no value it
    can take that means success other than nothing at all. ``tiers`` is the record of which
    peers came back with it, which is a different verdict from this one and is why it is
    written rather than returned.

    Carrying the id out is what the caller cannot otherwise have. This move fails about two
    different models and says which in its own line, so a bool left every sentence one level up
    naming the cortex whichever of the two the host actually refused. The retry, the give-up and
    the error an operator carries to the runbook now name the same tier this module's line does.

    The stop is of the model that was swapped in, and a host that does not carry that id has
    nothing to stop, so that one failure is skipped rather than retried. It is the difference
    between a slice of bad luck and a deployment that could never work: a swap into an unrostered
    tier fails at its start, and a restore that then treated the *same* 404 as a machine failure
    would abandon the cortex it had already evicted, twice, and end at the loudest failure in the
    design over a card that is in fact empty and idle.

    Two ``try`` blocks rather than one, because the two failures are about two different models
    and a field is only worth attaching when it is not a guess. The eviction is about the model
    the handoff swapped in; the start and its gate are both about the cortex, so they share a
    block and it stays unambiguous. A cortex that never gates answers the cortex too, for the
    same reason: the model that did not come up is the one the attempt failed on, whether the
    host said so or merely never finished.
    """
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
        state = await gate(plan.cortex_model)
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
    """Take the scope's own resident off the card, unless this host never had such a tier.

    Every other failure propagates to the caller's ``except``, because a model that is resident
    and will not stop is exactly the state the retry exists for.
    """
    try:
        await host.stop(model)
    except ModelNotHostedError as err:
        _logger.warning(
            "the model host does not serve this model, so there was nothing of it to stop",
            extra={"model": model, "error": str(err)},
        )


async def restart_evicted(host: ModelHost, plan: ResidencyPlan, tiers: StandingTiers) -> None:
    """Put back every tier a swap or a crash left evicted, so the standing residency is whole.

    A swap evicts the cortex AND any other hosted tier, because the deep model is alone on the
    GPU (ADR-0030 decision 8); an exit that restored the cortex alone would leave the subagent
    tier stopped for good while the conductor reopens admission to it, and the next delegated
    run would be placed on a server nothing ever restarted. Boot recovery's convergence ends here
    too, for the same tiers and by the same rule, which is why this is the one implementation.

    Deliberately after the cortex is serving and gated, and deliberately best effort: the turn
    the user is waiting on needs the cortex, and a tier that will not come back must not be
    reported as the cortex being gone, which is what failing the restore would say.

    Deliberately unconditional too, ``coresident`` included, where the swap in is not: a start
    against a tier the swap never stopped is a no-op the supervisor answers from its own child
    table, and if that tier died of its own accord while the deep model held the card, this is
    the one place that notices and brings it back.

    Best effort is not the same as unrecorded, which is the half that used to be missing: each
    outcome is written to ``tiers``, so a peer that refused to come back closes GPU placement and
    is retried, instead of admission reopening onto it and every spawn paying a dead attempt
    (``residency_tiers.py``). What an accepted ``start`` proves is only that the host took the
    request, exactly the evidence ``undrain`` has always reopened on: the peers are not gated
    here, because gating them would spend the load bound per tier inside the turn the user is
    waiting on.
    """
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
