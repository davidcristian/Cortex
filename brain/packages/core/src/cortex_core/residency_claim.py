"""The one-GPU-one-handoff rule, taken as a claim rather than checked as a precondition."""

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from cortex_core.errors import HandoffInProgressError


class HandoffClaim:
    """Whether a handoff already owns the swap sequence, claimed and released as a scope."""

    def __init__(self, condition: asyncio.Condition) -> None:
        self._condition = condition
        self._claimed = False

    @property
    def claimed(self) -> bool:
        """Whether a handoff owns the sequence right now, read without taking the condition."""
        return self._claimed

    @asynccontextmanager
    async def held(self) -> AsyncGenerator[None, None]:
        """Own the whole swap sequence for this block, or raise at once because another does."""
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
