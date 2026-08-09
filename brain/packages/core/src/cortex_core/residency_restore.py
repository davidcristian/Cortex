"""The swap back's own two guarantees: it is retried, and it finishes (ADR-0030 decision 4).

Split out of ``residency.py`` for the line cap, along a seam of its own: the manager owns when the
GPU may change hands, the lease every move runs under, and the state a move publishes, while this
owns what the swap back is *promised* to do once one has begun. ``restore_with_retries`` is the
policy (how many attempts, what is published between them, and what is true after the last one
fails); ``restore_uninterruptibly`` is the guarantee that outranks the caller's own teardown, and
it deliberately knows nothing about what a restore is, being handed one and made unabandonable.
"""

import asyncio
import logging
from collections.abc import Awaitable

from cortex_core.errors import ResidencyRestoreError
from cortex_core.model_host import ResidencyPlan
from cortex_core.ports import ModelHost, SubagentPlacer
from cortex_core.residency_charge import charge_standing
from cortex_core.residency_moves import ReadinessGate, restore_standing
from cortex_core.residency_state import (
    RESIDENCY_LOST,
    RESIDENCY_RESTORING,
    RESIDENCY_SERVING,
    ResidencyPublisher,
)

# How many times the swap back brings the cortex back before it gives up loudly: the first
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
    placer: SubagentPlacer | None,
) -> None:
    """Bring the cortex back, retrying once; give up loudly rather than silently.

    Called with the GPU lease held, so nothing can lease a half-restored card and any round the
    scope's own resident still had in flight has been waited out. ``publish`` is the manager's one
    residency writer, handed in rather than reached for, so every step of the give-up is visible
    to the seam at the instant it happens instead of after the exception unwinds.
    """
    cortex = plan.cortex_model
    await publish(None, RESIDENCY_RESTORING)
    for attempt in range(1, _RESTORE_ATTEMPTS + 1):
        if await restore_standing(host, plan, model, gate):
            await publish(cortex, RESIDENCY_SERVING)
            # Only here, where the cortex is genuinely serving again. A restore that gave up
            # leaves the handoff's charge standing, so spawns keep overflowing to the CPU rather
            # than being admitted onto a card nobody can describe.
            charge_standing(placer)
            return
        _logger.warning(
            "restoring the cortex failed; retrying",
            extra={"model": cortex, "attempt": attempt},
        )
    # Nothing is resident and no retry is left, so the report stops claiming a restore is under
    # way: Health goes on saying so until boot recovery converges residency again.
    await publish(None, RESIDENCY_LOST)
    _logger.error(
        "could not restore the cortex after a model swap; the GPU serves nothing",
        extra={"model": cortex, "attempts": _RESTORE_ATTEMPTS},
    )
    msg = (
        f"could not restore {cortex!r} after {_RESTORE_ATTEMPTS} attempts; manual "
        "recovery is needed (docs/runbooks/model-swap.md)"
    )
    raise ResidencyRestoreError(msg)


async def restore_uninterruptibly(restore: Awaitable[None]) -> None:
    """Run ``restore`` to completion even while this caller is being cancelled.

    The swap back is the recovery path, so it is the one thing a cancelled turn must not be able
    to abandon: a client that disconnects mid handoff would otherwise leave the deep model
    resident and the GPU serving nothing this process can lease again. It therefore runs as its
    own task behind a shield, and every cancellation waits for that task before it propagates,
    which keeps the ordering the residency scope promises (restored, then released).

    **Every** cancellation, not the first one, and that is the whole point of the loop: one
    shielded wait is abandoned by a second delivery, and the seam delivers two whenever a client
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
        # logged loudly inside, and the cancellation is what the caller must see.
        task.exception()
        raise cancelled
    await task
