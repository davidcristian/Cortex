"""Finishing the swap back however many times its caller is cancelled (ADR-0030 decision 4).

Split out of ``residency.py`` for the line cap, along a seam of its own: the manager owns when
the GPU may change hands and what the host is then asked to do, while this owns the single
guarantee that outranks the caller's own teardown. Nothing here knows what a restore *is*; it
is handed one and made uninterruptible.
"""

import asyncio
from collections.abc import Awaitable

from cortex_core.errors import ResidencyRestoreError


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
