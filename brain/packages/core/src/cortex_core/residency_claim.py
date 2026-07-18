"""The one-GPU-one-handoff rule, held as a claim rather than read as a precondition (ADR-0030)."""

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from cortex_core.errors import HandoffInProgressError


class HandoffClaim:
    """Whether a handoff already owns the swap sequence, claimed and released as a scope.

    Takes the manager's own condition rather than a lock of its own, so a claim and a residency
    scope can never be deciding about the same GPU at the same instant.
    """

    def __init__(self, condition: asyncio.Condition) -> None:
        self._condition = condition
        self._claimed = False

    @asynccontextmanager
    async def held(self) -> AsyncGenerator[None, None]:
        """Own the whole swap sequence for this block, or refuse at once because someone does.

        Releasing is a bare assignment on the way out, deliberately taking no lock: the release
        is owed even to a cancelled caller, and nothing waits on this claim to be woken.
        """
        async with self._condition:
            if self._claimed:
                msg = (
                    "a brain handoff is already in flight, so this one was not started (there "
                    "is one GPU)"
                )
                raise HandoffInProgressError(msg)
            self._claimed = True
        try:
            yield
        finally:
            self._claimed = False
