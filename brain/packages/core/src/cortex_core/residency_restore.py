"""The two guarantees of the swap back: it is retried, and it finishes."""

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
    """Bring the cortex back, retrying once; raise rather than returning quietly on failure."""
    cortex = plan.cortex_model
    await publish(None, RESIDENCY_RESTORING)
    # Rebound on every attempt, since the loop always runs at least once; this initial value
    # is what makes the failure path below typed.
    failed = cortex
    for attempt in range(1, _RESTORE_ATTEMPTS + 1):
        failed = await restore_standing(host, plan, model, gate, tiers)
        if failed is None:
            await publish(cortex, RESIDENCY_SERVING)
            # Charged only here, where the cortex is genuinely serving again. A restore that
            # stopped retrying leaves the handoff's charge in place, so spawns keep going to
            # the CPU rather than onto a card nothing can describe.
            charge_standing(tiers.placer)
            return
        _logger.warning(
            "restoring the cortex failed; retrying",
            extra={"model": cortex, "failed_model": failed, "attempt": attempt},
        )
    await publish(None, RESIDENCY_LOST)
    _logger.error(
        "could not restore the cortex after a model swap; the GPU serves nothing",
        extra={"model": cortex, "failed_model": failed, "attempts": _RESTORE_ATTEMPTS},
    )
    # The tier goes in the text as well as in the field beside it, because this string is also
    # the exception's message, read on a stream where no log formatter runs.
    msg = (
        f"could not restore {cortex!r} after {_RESTORE_ATTEMPTS} attempts, the last of which "
        f"failed on {failed!r}; manual recovery is needed (docs/runbooks/model-swap.md)"
    )
    raise ResidencyRestoreError(msg)


async def restore_uninterruptibly(restore: Awaitable[None]) -> None:
    """Run ``restore`` to completion even while this caller is being cancelled."""
    task = asyncio.ensure_future(restore)
    cancelled: asyncio.CancelledError | None = None
    while not task.done():
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError as err:
            # Raised below instead of here, so a restore failure cannot hide it: the caller
            # is being torn down and that is the more important thing to tell it about.
            cancelled = err
        except ResidencyRestoreError:
            pass
    if cancelled is not None:
        # Retrieved so asyncio does not warn about an unretrieved exception; the restore
        # failure was already logged inside, and the cancellation is what the caller must see.
        task.exception()
        raise cancelled
    await task
