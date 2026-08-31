"""The one-GPU-one-handoff rule, held as a claim rather than read as a precondition (ADR-0030).

Split out of ``residency.py`` along a seam that module's docstring already draws: the manager
owns the GPU lease and which model is resident, while this owns the separate question of whether
some escalating turn already owns the whole swap sequence. The two guard different flags and
answer different callers (the conductor claims before it drains; the scope's own guard is the
backstop underneath), so they are kept apart rather than sharing one method's body.

Why a claim and not a check: the conductor's precondition, read from a store and acted on two
awaits later, is a race that lets two handoffs into the prologue, after which the loser reopens
the drain window under the winner's resident deep model. Check and set therefore happen under one
lock with nothing awaited between them, and the loser is rejected while the machine is untouched,
which is what lets it be told that a handoff is running rather than that a swap failed.
"""

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

    @property
    def claimed(self) -> bool:
        """Whether a handoff owns the sequence right now, read without taking the condition.

        For the callers that must skip the pass rather than queue, which today is the tier sweep
        (``residency_sweep.py``). It is deliberately synchronous and lock free: a background pass
        that took the condition to ask would be waiting on the very handoff it is skipping for,
        and the answer it needs is only ever "not right now", which a stale ``False`` cannot
        produce (the flag is set under the condition before anything is drained).
        """
        return self._claimed

    @asynccontextmanager
    async def held(self) -> AsyncGenerator[None, None]:
        """Own the whole swap sequence for this block, or raise at once because another does.

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
