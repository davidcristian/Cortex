"""Getting the standing residency back without a turn: read the machine, publish if it agrees.

What one background pass does, in the two halves it has: this owns the **resident** half and
delegates the peers to ``residency_sweep.py``, under ``residency_heal.py``'s pacing and behind the
manager's fence. The resident half is the new one, and it exists for the one state the rest of the
design cannot leave on its own. A swap back that gave up publishes that nothing is resident
(``residency_restore.py``), so every ``acquire`` is refused, so no turn runs, so no handoff starts,
and the reconciliation a handoff would have run (``residency_watch.py``) is unreachable at exactly
the moment it is the thing that is needed. The same dead end has a cheaper twin: a boot that could
not confirm the cortex publishes that it did not come up, and a cortex that comes up a minute later
by itself leaves that sentence standing. Until this module the way out of either was to restart the
brain, which is what ``docs/runbooks/model-swap.md``'s manual recovery used to end with.

**It reads, and it publishes; it never converges.** ``swap_recovery.converge_residency`` is the
other thing that could be called here and it must not be: it stops and restarts every evictable
tier, so it would take down the peers a co-resident deployment keeps serving on purpose and would
interrupt a load already in flight. This asks ``status`` twice and writes one record instead.
Nothing on the card is touched, which is what makes it safe on a pass that runs every interval, and
what makes it free on a healthy deployment: a serving report returns before the first call.

**Two readings, because a serving cortex is not on its own the standing residency.** A restore can
give up at the stop as easily as at the start, so the deep model may still be holding the card when
the cortex comes back; publishing on the cortex's own state alone would then hand a lease out onto
a card that has two tiers on it, which on a 24 GB machine is how a spill or an OOM is arranged. The
deep tier is therefore observed off the card first, and a tier this daemon's roster never had
counts as off it, nothing being resident under a name that does not exist.

**What it will not do is start anything.** A cortex that is down stays down: this notices one that
is serving again, whoever brought it back (the operator through the sidecar's control API, which
the runbook's step 2 already tells them to use, or the daemon's own boot default after a restart).
Starting it here would put a whole tier load, minutes at tier scale, inside a pass that shutdown
waits out, and it would be a retry policy laid over an attempt that has already failed twice. That
is a decision of its own and it is written down rather than smuggled in here.
"""

import logging

from cortex_core.errors import ModelHostError, ModelNotHostedError
from cortex_core.model_host import ModelHostState, ResidencyPlan
from cortex_core.ports import ModelHost
from cortex_core.residency_board import ResidencyBoard
from cortex_core.residency_charge import charge_standing
from cortex_core.residency_state import RESIDENCY_SERVING, Fence
from cortex_core.residency_sweep import sweep_tiers
from cortex_core.residency_tiers import StandingTiers

_logger = logging.getLogger(__name__)


async def heal_standing_residency(
    host: ModelHost, plan: ResidencyPlan, board: ResidencyBoard, tiers: StandingTiers, fence: Fence
) -> None:
    """One pass over the standing residency: every evictable peer, and then the resident.

    The order is the argument for these being one pass rather than two loops. Both halves are a
    reading of the same machine taken at the same moment, and the resident's verdict is the one a
    probe actually reads, through a peer record ``StandingTiers.note_on`` composes into it, so the
    peers are refreshed first and the report that may name them is published second.
    """
    await sweep_tiers(host, plan, tiers, fence)
    await regain_residency(host, plan, board, tiers, fence)


async def regain_residency(
    host: ModelHost, plan: ResidencyPlan, board: ResidencyBoard, tiers: StandingTiers, fence: Fence
) -> None:
    """Publish the cortex as the resident again when the machine says it is, or do nothing.

    Never raises: this runs on a pass whose other half must still happen, and a host that cannot
    be asked is the very condition the report is already describing.

    The charge is the other half of the publish and lands with it. A restore that gave up leaves
    the handoff's VRAM charge standing on purpose, so that spawns overflow to the CPU rather than
    being admitted onto a card nobody can describe (``residency_charge.py``); the moment the card
    is described again, by the same reading that publishes, that reason is spent. It follows the
    publish with nothing awaited in between, so the two cannot be separated by a handoff.
    """
    if board.report.serving:
        return
    if not await _cortex_is_serving(host, plan.cortex_model):
        return
    if not await _deep_tier_is_off_the_card(host, plan.brain_model):
        return
    if await board.publish_between_handoffs(plan.cortex_model, RESIDENCY_SERVING, fence):
        charge_standing(tiers.placer)
        _logger.info(
            "the cortex is serving again, so residency was regained without a restart",
            extra={"model": plan.cortex_model},
        )


async def _cortex_is_serving(host: ModelHost, model: str) -> bool:
    """Whether the standing resident is actually answering right now.

    ``READY`` and nothing else, ``start`` being a spawn rather than a load: a cortex that is
    ``LOADING`` is the ordinary case a few seconds after somebody started it by hand, and the next
    pass is what publishes it. A host that cannot be asked, and a roster that has no such id, are
    both simply not evidence that it is serving.
    """
    try:
        return await host.status(model) is ModelHostState.READY
    except ModelHostError as err:
        _logger.debug(
            "the model host could not be asked whether the cortex is serving again: error=%s",
            err,
            extra={"model": model, "error": str(err)},
        )
        return False


async def _deep_tier_is_off_the_card(host: ModelHost, model: str) -> bool:
    """Whether the deep model is not holding the GPU, so a serving cortex is the standing shape.

    ``LOADING`` counts as on the card exactly as ``READY`` does: the weights are being allocated,
    which is the state a fit check exists to protect. ``STOPPED`` and ``FAILED`` are both off it,
    a process that died holding nothing, and a tier the daemon's roster never had is off it in the
    strongest sense there is. A host that could not answer leaves the report where it found it,
    which is the same posture the peer sweep takes for the same reason: no reading is not a
    reading that says yes.
    """
    try:
        state = await host.status(model)
    except ModelNotHostedError:
        return True
    except ModelHostError as err:
        _logger.debug(
            "the model host could not be asked whether the deep model is still resident: error=%s",
            err,
            extra={"model": model, "error": str(err)},
        )
        return False
    return state not in (ModelHostState.READY, ModelHostState.LOADING)
