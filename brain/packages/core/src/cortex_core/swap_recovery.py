"""Boot recovery: what a restart owes a handoff that a crash interrupted (ADR-0030 d4).

The conductor converges every path it is still running. This is the other half: the paths it
was NOT still running, because the process died mid-handoff. At startup the composition root
reads the one active record, marks it ``FAILED`` (kept under the store's TTL for diagnosis),
and converges residency so the cortex is the resident again whatever the GPU was left holding.

v1 deliberately does **not** auto-resume a brain phase. Without a request-identity/dedup design
a replay risks double-running side-effectful work (the hazard the seam-transport reconnect
entry sharpened), and losing an unfinished deep answer is the cheaper failure. Resume from the
record is the recorded refinement, unlocked by that same dedup design.

Nothing here raises: a boot that cannot reach the model host or the handoff store still serves.
Both failures are logged loudly, and both are visible the moment a turn actually needs the GPU,
which is more honest than refusing to start at all (the compose ``restart`` policy revives a
dead sidecar whose own boot default is cortex-up). What convergence does answer is whether the
cortex was **observed** serving when it finished, which the composition root publishes onto the
residency report: a log line nobody is reading is not a readiness surface, and the seam's very
first answer of the process must be that observation rather than an assumption (ADR-0030 d6).

That answer is about the **cortex** and about nothing else. The standing residency is the cortex
plus every tier a swap evicts, and a peer of it that will not start is recorded rather than
counted (``residency_tiers.py``), exactly as the swap back records one: a boot that reported the
usual assistant gone because a delegation tier refused would be the same conflation the swap back
refuses, on the surface where it is least excusable, since nobody has escalated yet.
"""

import logging

from cortex_core.errors import HandoffStoreError, ModelHostError
from cortex_core.handoff import HandoffState
from cortex_core.health_gate import await_model_ready
from cortex_core.model_host import ModelHostState, ResidencyPlan
from cortex_core.ports import Clock, HandoffStore, ModelHost, Sleeper
from cortex_core.residency_moves import restart_evicted
from cortex_core.residency_tiers import StandingTiers

_logger = logging.getLogger(__name__)


async def recover_handoffs(
    handoffs: HandoffStore,
    host: ModelHost,
    plan: ResidencyPlan,
    tiers: StandingTiers,
    *,
    clock: Clock,
    sleeper: Sleeper,
) -> bool:
    """Fail a crash-stranded handoff, converge the GPU, and answer whether the cortex serves.

    Called once at startup, before the seam serves, and only when escalation is enabled: a
    deployment that cannot escalate can have no stranded handoff and hosts nothing to converge.
    The bool is what the composition root publishes onto the residency report, so the seam's
    first answer of the process is an observation rather than the manager's optimistic seed.
    ``tiers`` is the manager's own peer record, handed in so the convergence below writes what it
    finds about the peers where every other writer writes it.
    """
    await _fail_stranded_handoff(handoffs)
    return await converge_residency(host, plan, tiers, clock=clock, sleeper=sleeper)


async def _fail_stranded_handoff(handoffs: HandoffStore) -> None:
    """Mark the one non-terminal record ``FAILED``; a handoff cannot outlive its process."""
    try:
        record = await handoffs.active()
        if record is None:
            return
        _logger.warning(
            "a handoff did not survive the restart; marking it failed",
            extra={"handoff": record.handoff_id, "state": record.state.value},
        )
        await handoffs.transition(record.handoff_id, HandoffState.FAILED)
    except HandoffStoreError:
        _logger.exception("could not read or fail a stranded handoff at startup")


async def converge_residency(
    host: ModelHost, plan: ResidencyPlan, tiers: StandingTiers, *, clock: Clock, sleeper: Sleeper
) -> bool:
    """Clear the GPU, settle the cortex on it, put the standing residency back, and report.

    Idempotent and boring on a clean boot: the deep model is already stopped, the cortex is
    already ``READY``, and nothing is touched. After a crash mid-handoff it is what puts the
    machine back where the conductor's ``finally`` would have left it, which is the same
    standing residency that ``finally`` restores: the cortex, and beside it every tier a swap
    evicts. The evictable tiers are stopped first and started last, because a crash can leave
    one holding VRAM the cortex needs before the cortex is the one thing that must come up.

    ``True`` only when the **cortex** was observed ``READY``, which is the whole point of
    answering at all: the caller publishes it, and a boot that could not confirm the cortex must
    not leave the seam claiming readiness. An unreachable host answers ``False`` for the same
    reason it is logged rather than raised: nothing was observed, and the honest report of an
    unobserved GPU is not a green one.

    The peers are outside that verdict at **both** ends, which is the whole of the fix here. Their
    clearing is best effort below, and their restart is the swap back's own move
    (``residency_moves.restart_evicted``), reused rather than repeated, so a start the host refuses
    marks the tier, closes GPU placement and joins the retry while the cortex's verdict stays a
    statement about the cortex. Measured against a real sidecar rather than reasoned about: the
    reachable misconfiguration is a tier named in ``CORTEX_SWAP_EVICT_MODELS`` that the daemon's
    roster has no artifact for, and that tier answers 404 to the **status** this asks first, so a
    fix that guarded only the restart would still have called the cortex gone.

    The deep model is deliberately not one of them. It is the other half of the residency the
    cortex has to be alone in, so a deep model that cannot be cleared is a reason to distrust
    everything after it, and its failure still answers ``False`` without asking about the cortex.

    The restart runs **after** the ``except``, also deliberately: a host that could not be reached
    was never asked to run a peer, and this record's one rule is that only a refusal marks.
    """
    for peer in plan.evict_models:
        await _clear_peer(host, peer)
    try:
        if await host.status(plan.brain_model) is not ModelHostState.STOPPED:
            _logger.warning(
                "stopping a model left running by an interrupted handoff",
                extra={"model": plan.brain_model},
            )
            await host.stop(plan.brain_model)
        settled = await _settle_cortex(host, plan, clock=clock, sleeper=sleeper)
    except ModelHostError:
        _logger.exception("the model host was unreachable during boot recovery")
        return False
    await restart_evicted(host, plan, tiers)
    return settled


async def _clear_peer(host: ModelHost, model: str) -> None:
    """Take one evictable peer off the card before the cortex loads, or say why it could not.

    The record is deliberately not written here even though this is where the failure is seen:
    the restart below asks every peer to run and is the one writer, so a tier that could not be
    stopped and then starts perfectly well is not a tier that is down. Anything genuinely missing
    is marked a few lines later by the same pass, from a ``start`` the host actually refused.
    """
    try:
        if await host.status(model) is not ModelHostState.STOPPED:
            _logger.warning(
                "stopping a model left running by an interrupted handoff", extra={"model": model}
            )
            await host.stop(model)
    except ModelHostError:
        _logger.exception(
            "a tier the standing residency includes could not be cleared at boot",
            extra={"model": model},
        )


async def _settle_cortex(
    host: ModelHost, plan: ResidencyPlan, *, clock: Clock, sleeper: Sleeper
) -> bool:
    """Make sure the cortex is serving, say so loudly when it will not be, and answer which."""
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
