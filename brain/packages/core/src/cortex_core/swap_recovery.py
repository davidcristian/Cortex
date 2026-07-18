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
dead sidecar whose own boot default is cortex-up).
"""

import logging

from cortex_core.errors import HandoffStoreError, ModelHostError
from cortex_core.handoff import HandoffState
from cortex_core.health_gate import await_model_ready
from cortex_core.model_host import ModelHostState, ResidencyPlan
from cortex_core.ports import Clock, HandoffStore, ModelHost, Sleeper

_logger = logging.getLogger(__name__)


async def recover_handoffs(
    handoffs: HandoffStore, host: ModelHost, plan: ResidencyPlan, *, clock: Clock, sleeper: Sleeper
) -> None:
    """Fail a crash-stranded handoff and converge the GPU back onto the cortex.

    Called once at startup, before the seam serves, and only when escalation is enabled: a
    deployment that cannot escalate can have no stranded handoff and hosts nothing to converge.
    """
    await _fail_stranded_handoff(handoffs)
    await converge_residency(host, plan, clock=clock, sleeper=sleeper)


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
    host: ModelHost, plan: ResidencyPlan, *, clock: Clock, sleeper: Sleeper
) -> None:
    """Clear the GPU, settle the cortex on it, and put the standing residency back.

    Idempotent and boring on a clean boot: the deep model is already stopped, the cortex is
    already ``READY``, and nothing is touched. After a crash mid-handoff it is what puts the
    machine back where the conductor's ``finally`` would have left it, which is the same
    standing residency that ``finally`` restores: the cortex, and beside it every tier a swap
    evicts. The evictable tiers are stopped first and started last, because a crash can leave
    one holding VRAM the cortex needs before the cortex is the one thing that must come up.
    """
    try:
        for model in (*plan.evict_models, plan.brain_model):
            if await host.status(model) is not ModelHostState.STOPPED:
                _logger.warning(
                    "stopping a model left running by an interrupted handoff",
                    extra={"model": model},
                )
                await host.stop(model)
        await _settle_cortex(host, plan, clock=clock, sleeper=sleeper)
        for model in plan.evict_models:
            await host.start(model)
    except ModelHostError:
        _logger.exception("the model host was unreachable during boot recovery")


async def _settle_cortex(
    host: ModelHost, plan: ResidencyPlan, *, clock: Clock, sleeper: Sleeper
) -> None:
    """Make sure the cortex is serving, and say so loudly when it will not be."""
    if await host.status(plan.cortex_model) is ModelHostState.READY:
        return
    await host.start(plan.cortex_model)
    state = await await_model_ready(
        host, plan.cortex_model, clock=clock, sleeper=sleeper, plan=plan
    )
    if state is not ModelHostState.READY:
        _logger.error(
            "the cortex is not serving after boot recovery; turns will fail until it is",
            extra={"model": plan.cortex_model, "state": state.value},
        )
