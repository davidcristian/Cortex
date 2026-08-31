"""Boot recovery: what a restart owes a handoff that a crash interrupted (ADR-0030 d4).

The conductor converges every path it is still running; this module covers the paths it was not,
because the process died mid-handoff. At startup the composition root reads the one active record,
marks it ``FAILED`` (kept under the store's TTL for diagnosis), and converges residency so the
cortex is the resident again whatever the GPU was left holding.

A brain phase is deliberately not auto-resumed. Without a request-identity and dedup design a
replay risks double-running side-effectful work, and losing an unfinished deep answer is the
cheaper failure. Resume from the record is a recorded refinement, unlocked by that same design.

Nothing here raises: a boot that cannot reach the model host or the handoff store still serves,
both failures are logged, and both show up again the moment a turn needs the GPU. What convergence
returns is whether the cortex was observed serving when it finished, which the composition root
publishes onto the residency report, so the seam's first answer of the process is that observation
rather than an assumption (ADR-0030 d6).

``docs/modules/brain-core.md`` argues the two boundaries around that answer: why a tier a swap
evicts stays outside the cortex's verdict at both ends (``residency_tiers.py`` holds the record
instead), and why the deep model's clearing stays fatal except for a tier the host does not carry
at all, which is a configuration fact rather than a health reading (ADR-0030 unrostered-tier
addendum).
"""

import logging

from cortex_core.errors import HandoffStoreError, ModelHostError, ModelNotHostedError
from cortex_core.handoff import HandoffState
from cortex_core.health_gate import await_model_ready
from cortex_core.model_host import ModelHostState, ResidencyPlan
from cortex_core.ports import Clock, HandoffStore, ModelHost, Sleeper
from cortex_core.residency_moves import restart_evicted
from cortex_core.residency_tiers import StandingTiers
from cortex_core.swap_reasons import STRANDED_REASON

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
    The bool is what the composition root publishes onto the residency report, so the seam's first
    answer of the process is an observation rather than the manager's seed. ``tiers`` is the
    manager's own peer record, handed in so the convergence below writes what it finds about the
    peers where every other writer writes it.
    """
    await _fail_stranded_handoff(handoffs)
    return await converge_residency(host, plan, tiers, clock=clock, sleeper=sleeper)


async def _fail_stranded_handoff(handoffs: HandoffStore) -> None:
    """Mark the one non-terminal record ``FAILED``, saying so on the record as well as here.

    This is the one settle whose writer is definitely not the process that ran the handoff, so the
    log line below and the record's own reason serve two different readers rather than being two
    copies for one. The line names the stranded work ``turn_id``, a handoff id being the escalating
    turn's id (``handoff.py``), so a reader can carry the id off this line into the previous boot's
    record of that turn (ADR-0009 sixth-name addendum). It names the conversation too, which is
    what makes the line reachable at all: the turn it strands died with the process that ran it, so
    nobody is holding its id, while the chat it belonged to is still on somebody's screen (ADR-0009
    named-conversation addendum). The residency lines below name neither, being about the card
    rather than about any one handoff.
    """
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
    host: ModelHost, plan: ResidencyPlan, tiers: StandingTiers, *, clock: Clock, sleeper: Sleeper
) -> bool:
    """Clear the GPU, settle the cortex on it, put the standing residency back, and report.

    Idempotent on a clean boot: the deep model is already stopped, the cortex is already ``READY``,
    and nothing is touched. After a crash mid-handoff this puts the machine back where the
    conductor's ``finally`` would have left it, on the same standing residency that ``finally``
    restores: the cortex, and beside it every tier a swap evicts. The evictable tiers are stopped
    first and started last, because a crash can leave one holding VRAM the cortex needs before the
    cortex itself can load.

    Returns ``True`` only when the cortex was observed ``READY``. An unreachable host returns
    ``False`` for the same reason the failure is logged rather than raised: nothing was observed,
    and an unobserved GPU cannot be reported ready. A cortex the host does not carry returns
    ``False`` too, separated from an unreachable host in the log only, since the two share an
    operator's next move of reading the daemon's roster.

    The evictable peers stay outside that verdict at both ends. Their clearing is best effort
    below, and their restart is the swap back's own ``residency_moves.restart_evicted``, reused
    rather than repeated, so a ``start`` the host rejects marks the tier, closes GPU placement and
    joins the retry while the cortex's verdict stays a statement about the cortex. Both ends are
    needed because a tier named in ``CORTEX_SWAP_EVICT_MODELS`` that the daemon's roster has no
    artifact for answers 404 to the ``status`` asked first as well as to the ``start``, so guarding
    only the restart would still have reported the cortex gone. The deep model is not a peer and
    its clearing stays fatal, the one exception being a tier the host does not carry at all
    (``_clear_deep``).

    Two ordering constraints hold the shape. The restart runs after the ``except`` arms, because a
    host that could not be reached was never asked to run a peer, and only a rejected ``start``
    marks one. The clearing and the settling sit in separate ``try`` blocks so that each log line
    names the model of the one call its block wraps, rather than either of the two models it could
    otherwise have been.
    """
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
    """Take the deep model off the card, or say why this host has no such tier to take off.

    Everything but the last case propagates: a deep model that is resident and will not stop leaves
    the cortex unable to have the card to itself, and a host that cannot be asked leaves nothing
    observed at all, so neither may be reported as a clean boot.

    A tier the host does not carry is different. The daemon builds its roster from its own env at
    startup (``CORTEX_MODEL_FILE_BRAIN`` naming no artifact leaves the deep tier out of it), so the
    answer is a 404 for the life of that container and no later boot gets a different one. Nothing
    is holding the GPU under a name nothing can start, so the cortex is asked about normally and
    the deployment is told once, here, that the escalation it declared cannot happen.
    """
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
    """Take one evictable peer off the card before the cortex loads, or say why it could not.

    The peer record is deliberately not written here even though this is where the failure is seen.
    The restart below asks every peer to run and is the one writer, so a tier that could not be
    stopped and then starts perfectly well is not recorded as down. Anything genuinely missing is
    marked a few lines later by that pass, from a ``start`` the host rejected.
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
