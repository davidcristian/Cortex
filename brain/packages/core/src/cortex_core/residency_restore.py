"""Finishing the swap back however many times its caller is cancelled (ADR-0030 decision 4)."""

import asyncio
from collections.abc import Awaitable

from cortex_core.errors import ResidencyRestoreError


async def restore_uninterruptibly(restore: Awaitable[None]) -> None:
    """Run ``restore`` to completion even while this caller is being cancelled."""
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
