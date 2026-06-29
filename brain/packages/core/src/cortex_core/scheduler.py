"""SubagentScheduler v1: a pure bounded-concurrency admission gate (asyncio, no I/O, see ADR-0010).
"""

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager


class ConcurrencyScheduler:
    """SubagentScheduler v1: admit up to ``max_concurrency`` subagents at once, queue the rest."""

    def __init__(self, max_concurrency: int) -> None:
        if max_concurrency < 1:
            msg = f"max_concurrency must be >= 1, got {max_concurrency}"
            raise ValueError(msg)
        self._semaphore = asyncio.Semaphore(max_concurrency)

    @asynccontextmanager
    async def admit(self) -> AsyncGenerator[None, None]:
        """Acquire one CPU slot for the block's duration; wait when the budget is full."""
        async with self._semaphore:
            yield
