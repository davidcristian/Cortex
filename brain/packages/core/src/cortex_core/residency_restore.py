"""The swap back's own two guarantees: it is retried, and it finishes (ADR-0030 decision 4).

Split out of ``residency.py`` for the line cap, along a seam of its own: the manager owns when the
resident model may change, the lease every move runs under, and the state a move publishes, while
this owns what the swap back is promised to do once one has begun. ``restore_with_retries`` is the
policy (how many attempts, what is published between them, and what is true after the last one
fails); ``restore_uninterruptibly`` is the guarantee that outranks the caller's own teardown, and
it deliberately has no knowledge of what a restore is: it is handed one and makes it
unabandonable.
"""

import asyncio
import logging
from collections.abc import Awaitable

from cortex_core.errors import ResidencyRestoreError
from cortex_core.model_host import ResidencyPlan
from cortex_core.ports import ModelHost
from cortex_core.residency_charge import charge_standing
from cortex_core.residency_moves import ReadinessGate, restore_standing
from cortex_core.residency_state import (
    RESIDENCY_LOST,
    RESIDENCY_RESTORING,
    RESIDENCY_SERVING,
    ResidencyPublisher,
)
from cortex_core.residency_tiers import StandingTiers

# How many times the swap back brings the cortex back before it raises: the first
# attempt plus the one retry ADR-0030 decision 4 step 3 specifies. A third would not be a
# different experiment; past two, the host itself is gone and only the runbook helps.
_RESTORE_ATTEMPTS = 2

_logger = logging.getLogger(__name__)


async def restore_with_retries(
    host: ModelHost,
    plan: ResidencyPlan,
    model: str,
    gate: ReadinessGate,
    publish: ResidencyPublisher,
    tiers: StandingTiers,
) -> None:
    """Bring the cortex back, retrying once; raise rather than returning quietly on failure.

    Called with the GPU lease held, so nothing can lease a half-restored card and any round the
    scope's own resident still had in flight has been waited out. ``publish`` is the manager's one
    residency writer, handed in rather than reached for, so every step of the failure is visible
    to the seam at the instant it happens instead of after the exception unwinds. ``tiers`` is
    the same shape of argument for the peers: the record of which of them came back, written
    where the attempt is made rather than inferred afterwards from a machine nobody re-reads. It
    carries the placer too, which is the one collaborator the standing charge below needs.

    Each attempt answers the model it failed on rather than a bool, and that id is what lets each
    line here name the right tier. The swap back has two subjects, the resident it is taking off
    the card and the cortex it is putting back, so an answer that only said "no" left every
    sentence here naming the cortex whichever of them actually failed, including the failure an
    operator reads out of the runbook.
    """
    cortex = plan.cortex_model
    await publish(None, RESIDENCY_RESTORING)
    # The floor the give-up below needs to be typed: the attempt count is a positive constant, so
    # the loop always runs and always rebinds this, and what stands here is exactly what both
    # sentences said before an attempt could name the tier it failed on.
    failed = cortex
    for attempt in range(1, _RESTORE_ATTEMPTS + 1):
        failed = await restore_standing(host, plan, model, gate, tiers)
        if failed is None:
            await publish(cortex, RESIDENCY_SERVING)
            # Only here, where the cortex is genuinely serving again. A restore that stopped
            # retrying leaves the handoff's charge in place, so spawns keep overflowing to the CPU
            # rather than being admitted onto a card nobody can describe.
            charge_standing(tiers.placer)
            return
        # Two model fields, because they are two facts and either can be the one to act on: the
        # sentence is about restoring the cortex, which is what ``model`` has always named here,
        # while ``failed_model`` is the tier this attempt actually failed on and may be the
        # handoff's own resident, which the swap back stops before it starts anything.
        _logger.warning(
            "restoring the cortex failed; retrying",
            extra={"model": cortex, "failed_model": failed, "attempt": attempt},
        )
    # Nothing is resident and no retry is left, so the report stops claiming a restore is under
    # way: Health goes on saying so until boot recovery converges residency again.
    await publish(None, RESIDENCY_LOST)
    _logger.error(
        "could not restore the cortex after a model swap; the GPU serves nothing",
        extra={"model": cortex, "failed_model": failed, "attempts": _RESTORE_ATTEMPTS},
    )
    # The one sentence an operator carries to the runbook, so the tier goes in the prose as well
    # as in the field beside it: this string is also the exception's text, read on a stream where
    # no formatter runs, and "could not restore the cortex" sent a reader after the wrong model
    # every time it was the eviction that failed.
    msg = (
        f"could not restore {cortex!r} after {_RESTORE_ATTEMPTS} attempts, the last of which "
        f"failed on {failed!r}; manual recovery is needed (docs/runbooks/model-swap.md)"
    )
    raise ResidencyRestoreError(msg)


async def restore_uninterruptibly(restore: Awaitable[None]) -> None:
    """Run ``restore`` to completion even while this caller is being cancelled.

    The swap back is the recovery path, so it is the one thing a cancelled turn must not be able
    to abandon: a client that disconnects mid handoff would otherwise leave the deep model
    resident and the GPU serving nothing this process can lease again. It therefore runs as its
    own task behind a shield, and every cancellation waits for that task before it propagates,
    which keeps the ordering the residency scope promises (restored, then released).

    Every cancellation, not only the first, which is what the loop is for: one shielded wait is
    abandoned by a second delivery, and the seam delivers two whenever a client
    ``Cancel`` is followed by the stream's own teardown (``ConverseStream`` cancels the turn from
    the pump, then again from ``events()``'s ``finally``). A restore left running behind the
    scope's exit is the harm: the conductor reopens subagent admission the moment the scope
    returns, so admission would reopen onto a cortex still stopped and a tier not yet restarted.
    The wait is bounded by the restore itself, not by the number of cancellations, since every
    iteration makes the same progress the first one did.
    """
    task = asyncio.ensure_future(restore)
    cancelled: asyncio.CancelledError | None = None
    while not task.done():
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError as err:
            cancelled = err
        except ResidencyRestoreError:
            # Raised below instead, so that a cancellation delivered first still wins: the
            # caller is being torn down and that is the graver thing to tell it about.
            pass
    if cancelled is not None:
        # Retrieved so asyncio does not warn about it; a restore failure has already been
        # logged inside, and the cancellation is what the caller must see.
        task.exception()
        raise cancelled
    await task
